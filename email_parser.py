import logging
import google.generativeai as genai
from bs4 import BeautifulSoup
import numpy as np
from dotenv import load_dotenv
import os
from sentence_transformers import SentenceTransformer
import json
import re

load_dotenv()
logger = logging.getLogger(__name__)

# Configure the Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro')

# Initialize the sentence transformer model
sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

# List to store processed articles with their embeddings
processed_articles = []

def extract_content_with_links(email):
    """
    Extracts text content from email while preserving links and their context.
    """
    soup = BeautifulSoup(email.html or email.text, 'html.parser')
    content = []
    for element in soup.descendants:
        if element.name == 'a' and element.get('href'):
            content.append(f"{element.get_text()} [LINK: {element.get('href')}]")
        elif element.string and element.string.strip():
            content.append(element.string.strip())
    return ' '.join(content)

def extract_articles(email):
    """
    Extracts individual articles from an email using Gemini 1.5 Pro.
    Returns a list of dictionaries, each containing article title, description, and URL.
    """
    logger.info(f"Extracting articles from email: {email.subject}")
    
    # Extract text content from email with links
    text_content = extract_content_with_links(email)
    
    # Use Gemini to extract articles
    prompt = f"""
    Analyze the following email content and extract information about articles mentioned.
    For each article:
    1. Extract the original title, description (if available), and URL (look for [LINK: url] in the text)
    2. Rewrite the title and description in a friendlier, lighter tone with a touch of personal feel
    3. Keep the rewritten content concise and engaging

    Email content:
    {text_content}

    Format the output as a JSON array of objects, each with 'title', 'description', and 'url' keys.
    The 'title' and 'description' should contain the rewritten versions.
    Ensure that the output is valid JSON. If no URL is found for an article, use an empty string for the 'url' value.

    Example of the tone and style for rewritten content:
    Original: "Implementing Machine Learning Models: A Comprehensive Guide"
    Rewritten: "Dive into ML: Your Friendly Guide to Bringing Models to Life!"

    Original: "This article provides a detailed walkthrough of implementing various machine learning models, covering data preparation, model selection, and deployment strategies."
    Rewritten: "Ready to make your ML dreams a reality? We've got you covered with easy steps from prepping your data to picking the perfect model. Let's turn those algorithms into action!"
    """
    
    response = model.generate_content(prompt)
    
    try:
        # Extract JSON from the response
        json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            articles = json.loads(json_str)
        else:
            raise ValueError("No JSON array found in the response")
        
        # Validate the structure of each article
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

def get_embedding(text):
    """
    Get the embedding for a given text using sentence-transformers.
    """
    return sentence_model.encode(text)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def is_duplicate_article(article, threshold=0.95):
    """
    Check if an article is a duplicate based on semantic similarity.
    """
    article_text = f"{article['title']} {article['description']}"
    article_embedding = get_embedding(article_text)
    
    for processed_article, processed_embedding in processed_articles:
        similarity = cosine_similarity(article_embedding, processed_embedding)
        if similarity > threshold:
            logger.info(f"Duplicate article found: {article['title']} (Similarity: {similarity:.2f})")
            return True
    
    processed_articles.append((article, article_embedding))
    return False

def extract_content(email):
    """
    Extracts content from an email, deduplicates articles, and returns unique articles with embeddings.
    """
    logger.info(f"Extracting content from email: {email.subject}")
    articles = extract_articles(email)
    
    unique_articles = []
    for article in articles:
        if not is_duplicate_article(article):
            article_text = f"{article['title']} {article['description']}"
            article['embedding'] = get_embedding(article_text)
            unique_articles.append(article)
        else:
            logger.info(f"Skipping duplicate article: {article['title']}")
    
    return unique_articles

def clear_processed_articles():
    global processed_articles
    processed_articles.clear()
