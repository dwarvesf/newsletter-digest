import logging
import google.generativeai as genai
import os
import json
import re
from config_manager import get_search_criteria, get_min_relevancy_score
from datetime import datetime
from email.utils import parsedate_to_datetime
from article_summarize import crawl_and_summarize
from promts import get_extract_articles_prompt
logger = logging.getLogger(__name__)

# Configure the Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro')

def extract_articles(email):
    """
    Extracts individual articles from an email using Gemini 1.5 Pro.
    Returns a list of dictionaries, each containing article title, description, and URL.
    """
    logger.info(f"Extracting articles from email: {email.subject}")
    
    # Get grouped criteria
    grouped_criteria = get_search_criteria()
    
   
    
    logger.info("Requesting Gemini to extract articles from email")
    prompt = get_extract_articles_prompt(email.text or email.html, grouped_criteria, get_min_relevancy_score(),True)
    response = model.generate_content(prompt)
    
    try:
        json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            articles = json.loads(json_str)
        else:
            raise ValueError("No JSON array found in the response")
        need_enrichment_articles = [article for article in articles if article.get('need_enrichment', True)]

        if len(need_enrichment_articles) > 0:
            logger.info(f"Starting to crawl {len(need_enrichment_articles)} other articles")
            for article in need_enrichment_articles:
                summary = crawl_and_summarize(article.get('url'))
                article['summary'] = summary

        need_enrichment_article_prompt_content = "__".join([f"{article.get('title')},{article.get('url')},{article.get('summary')}." for article in need_enrichment_articles])
        enrichment_prompt = get_extract_articles_prompt(need_enrichment_article_prompt_content, grouped_criteria, get_min_relevancy_score())
        logger.info("Requesting Gemini to extract other articles from email")

        enrichment_response = model.generate_content(enrichment_prompt)

        try:
            enrichment_json_match = re.search(r'\[.*\]', enrichment_response.text, re.DOTALL)
            if enrichment_json_match:
                enrichment_json_str = enrichment_json_match.group(0)

                enrichment_articles = json.loads(enrichment_json_str)
                articles.extend(enrichment_articles)
            else:
                raise ValueError("No JSON array found in the response")
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")

        articles = [article for article in articles if not article.get('need_enrichment', True)]
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from Gemini response: {str(e)}")
        articles = []
    except ValueError as e:
        logger.error(f"Error in Gemini response structure: {str(e)}")
        articles = []
    except Exception as e:
        logger.error(f"Unexpected error parsing Gemini response: {str(e)}")
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
