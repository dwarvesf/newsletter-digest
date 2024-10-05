import logging
import google.generativeai as genai
import os
import json
import re
from config_manager import get_search_criteria, get_min_relevancy_score
from datetime import datetime
from email.utils import parsedate_to_datetime

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
    
    prompt = f"""
    Analyze the following email content and extract information about articles mentioned.
    For each article:
    1. Extract the original title, description (if available), and URL (look for [LINK: url] in the text)
    2. Rewrite the title and description in a friendlier, lighter tone with a touch of personal feel
    3. Keep the rewritten content concise and engaging
    4. Restrict the description to be less than 160 characters, and be more to the point
    5. Generate an array of criteria that the article matches, along with a relevancy score (0-1) for each individual criterion
      a. Ignore articles that read like
        i. A GitHub release or update
        ii. A sponsorship or donation request
        iii. An advertisement
      b. Prioritize articles that are news, research papers, or have a significant and unique contribution to the field
      c. Save 0.9 and above for the most relevant articles, following the above guidelines
      d. Use up to 2 decimal places for the relevancy scores
    6. Only include criteria with relevancy scores above {get_min_relevancy_score()}

    Email content:
    {email.text or email.html}

    Format the output as a JSON array of objects, each with 'title', 'description', 'url', and 'criteria' keys.
    The 'title' and 'description' should contain the rewritten versions.
    The 'criteria' should be an array of objects, each with 'name' and 'score' keys.
    Ensure that the output is valid JSON. If no URL is found for an article, use an empty string for the 'url' value.

    Use the following list of criteria, but return them as individual items, not grouped:
    {grouped_criteria}

    Example of the tone and style for rewritten content:
    Original: "Implementing Machine Learning Models: A Comprehensive Guide"
    Rewritten: "Dive into ML: Your Friendly Guide to Bringing Models to Life!"

    Original: "This article provides a detailed walkthrough of implementing various machine learning models, covering data preparation, model selection, and deployment strategies."
    Rewritten: "Ready to make your ML dreams a reality? We've got you covered with easy steps from prepping your data to picking the perfect model. Let's turn those algorithms into action!"

    Example of criteria output:
    "criteria": [
        {{"name": "Typescript", "score": 0.95}},
        {{"name": "Javascript", "score": 0.90}},
        {{"name": "React", "score": 0.80}}
    ]
    """
    
    logger.info("Requesting Gemini to extract articles from email")

    response = model.generate_content(prompt)
    
    try:
        json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            articles = json.loads(json_str)
        else:
            raise ValueError("No JSON array found in the response")
        
        for article in articles:
            if not all(key in article for key in ('title', 'description', 'url')):
                raise ValueError(f"Invalid article structure: {article}")
        
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
