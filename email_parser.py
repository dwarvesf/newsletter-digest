import logging
import os
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from config_manager import get_search_criteria, get_min_relevancy_score, get_openai_model_name, get_openai_rate_limit
from datetime import datetime
from email.utils import parsedate_to_datetime
from promts import get_extract_articles_prompt
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional

logger = logging.getLogger(__name__)

# Configure OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
model_name = get_openai_model_name()

# Rate limiter variables
last_api_call_time = 0
rate_limit_interval = 60 / get_openai_rate_limit()

def create_session_with_retries(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """Create a session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def get_seo_description(url: str) -> str:
    """Fetch SEO description from article URL using multiple meta tag formats"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extended list of meta tag formats
        meta_tag_attrs = [
            {'name': 'description'},
            {'property': 'og:description'},
            {'name': 'twitter:description'},
            {'name': 'dc.description'},      # Dublin Core
            {'name': 'Description'},          # Capitalized variant
            {'property': 'description'},      # Alternative property
            {'itemprop': 'description'},      # Schema.org
            {'name': 'dcterms.description'},  # Dublin Core Terms
            {'name': 'abstract'}             # Academic content
        ]
        
        # Try all meta tag formats
        for attrs in meta_tag_attrs:
            tag = soup.find('meta', attrs=attrs)
            if tag and tag.get('content'):
                return tag['content'].strip()
        
        # Fallback to first paragraph if no meta description
        first_p = soup.find('p')
        if first_p:
            return first_p.get_text().strip()[:200] + '...'
        
        return ""
    except Exception as e:
        logger.error(f"Error fetching SEO description for {url}: {str(e)}")
        return ""

def get_article_content(url: str, timeout: int = 20, retries: int = 3) -> str:
    """
    Fetch article content using Jina AI REST API and parse the response
    
    Args:
        url (str): The URL to fetch content from
        timeout (int): Request timeout in seconds
        retries (int): Number of retries for failed requests
        
    Returns:
        str: Article content text after 'Markdown Content:' line
    """
    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            'Authorization': f'Bearer {os.getenv("JINA_API_KEY")}',
        }
        
        session = create_session_with_retries(retries=retries)
        
        response = session.get(
            jina_url, 
            headers=headers, 
            timeout=(timeout, timeout)
        )
        response.raise_for_status()

        content_lines = []
        found_markdown = False
        
        for line in response.text.split('\n'):
            if line.startswith('Markdown Content:'):
                found_markdown = True
                continue
            if found_markdown and line.strip():
                content_lines.append(line.strip())
        
        return '\n'.join(content_lines) if content_lines else ""
            
    except requests.Timeout as e:
        logger.error(f"Timeout fetching content from Jina AI for {url}: {str(e)}")
        return ""
    except requests.ConnectionError as e:
        logger.error(f"Connection error with Jina AI for {url}: {str(e)}")
        return ""
    except requests.RequestException as e:
        logger.error(f"Request failed for Jina AI for {url}: {str(e)}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error fetching content from Jina AI for {url}: {str(e)}")
        return ""

def extract_articles(email):
    global last_api_call_time
    articles = []

    logger.info(f"Extracting articles from email: {email.subject}")
    
    # Get grouped criteria
    grouped_criteria = get_search_criteria()
    
    # Ensure rate limit is respected
    current_time = time.time()
    time_since_last_call = current_time - last_api_call_time
    if time_since_last_call < rate_limit_interval:
        sleep_time = rate_limit_interval - time_since_last_call
        logger.info(f"Rate limit exceeded, sleeping for {sleep_time:.2f} seconds")
        time.sleep(sleep_time)
    
    logger.info("Requesting OpenAI to extract articles from email")
    prompt = get_extract_articles_prompt(email.text or email.html, grouped_criteria, get_min_relevancy_score())
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts articles from newsletter emails and returns them in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        last_api_call_time = time.time()

        # Parse the response content
        response_content = response.choices[0].message.content
        parsed_response = json.loads(response_content)
        
        # Expect articles to be in a key called 'articles'
        if 'articles' in parsed_response:
            articles = parsed_response['articles']
        else:
            raise ValueError("Response missing 'articles' key")

        # Filter articles and fetch descriptions if missing
        processed_articles = []
        for article in articles:
            if isinstance(article.get('criteria'), list):
                logger.info(f"Fetching content for {article['url']}")
                content = get_article_content(article['url'])
                if content:
                     article['raw_content']=content
                # Fallback to SEO description if Jina fails
                if not article['description']:
                    logger.info(f"Falling back to SEO description for {article['url']}")
                    article['description'] = get_seo_description(article['url'])
                
                processed_articles.append(article)
        
        articles = processed_articles

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from OpenAI response: {str(e)}")
        articles = []
    except ValueError as e:
        logger.error(f"Error in OpenAI response structure: {str(e)}")
        articles = []
    except Exception as e:
        logger.error(f"Unexpected error parsing OpenAI response: {str(e)}")
        articles = []
    
    logger.info(f"Extracted {len(articles)} articles from the email")
    return articles

def parse_date(date_str):
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822 format
            '%Y-%m-%d %H:%M:%S',
            '%d %b %Y %H:%M:%S %z',
            '%a, %d %b %Y %H:%M:%S',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
    
    raise ValueError(f"Unable to parse date string: {date_str}")
