"""
This module is responsible for connecting to the email server, fetching unread emails,
processing them, and saving the processed content using Google Cloud Storage.
"""

import os
from imap_tools import MailBox, AND, OR, MailMessageFlags
from datetime import datetime
from config_manager import get_allowed_senders
import logging
import socket
from email_parser import extract_articles, parse_date
from dotenv import load_dotenv
from storage import StorageUtil
from typing import List
import pandas as pd
from content_sanitizer import ContentSanitizer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("newsletter_bot.log"),
        logging.StreamHandler()
    ]
)

load_dotenv()

logger = logging.getLogger(__name__)

def fetch_unread_emails():
    """
    Connects to the IMAP server, fetches unread emails from allowed senders,
    processes them, and saves the processed content using Google Cloud Storage.
    """
    email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')
    imap_server = os.getenv('IMAP_SERVER')
    allowed_senders = get_allowed_senders()

    logger.info(f"Connecting to IMAP server: {imap_server}")
    logger.info("Fetching unread emails")

    try:
        articles= []
        with MailBox(imap_server, port=993).login(email, password) as mailbox:
            sender_filter = OR(*[f'FROM "{sender}"' for sender in allowed_senders])
            unread_filter = 'UNSEEN'
            
            logger.info("Applying filters and fetching emails")
            
            emails = list(mailbox.fetch(AND(sender_filter, unread_filter)))
            logger.info(f"Fetched {len(emails)} unread emails")

            # Sort emails by date (older to newer)
            emails.sort(key=lambda x: parse_date(x.date_str))
          
            # Collect raw contents for sanitization after processing emails
            for email in emails:
                try:
                    # Process email and collect raw content
                    new_articles = process_and_save_email(email)
                    articles.extend(new_articles)

                    # Mark email as read if processing was successful
                    mailbox.flag(email.uid, MailMessageFlags.SEEN, True)
                except Exception as e:
                    logger.error(f"Failed to process email {email.subject}: {str(e)}")
                    # Ensure the email remains unread for the next fetch
                    mailbox.flag(email.uid, MailMessageFlags.SEEN, False)

        # Sanitize content after closing the mailbox connection
        # if len(articles) > 0:
        #     logger.info(f"Sanitizing {len(articles)} articles")
        #     sanitize_content(articles)

    except socket.error as e:
        logger.error(f"Socket error: {str(e)}")
    except Exception as e:
        logger.error(f"Error connecting to email server: {str(e)}")

def process_and_save_email(email):
    """
    Processes a single email, extracts articles, and saves them to Parquet format.
    Ensures articles are unique by URL.
    """
    # Extract articles from email
    articles = extract_articles(email)
    storage = StorageUtil()

    # Define the current date internally within the function
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Use current_date for file paths and other operations
    filepath = f'newsletter-digest/{current_date}.parquet'

    # Get existing articles for today
    try:
        existing_df = pd.DataFrame(storage.read_data(filepath))
    except:
        existing_df = pd.DataFrame()

    # Prepare new articles, ensuring URL uniqueness
    new_articles = []
    seen_urls = set()  # Track URLs we've already processed

    for article in articles:
        url = article['url'].split('?')[0]  # Clean URL
        
        # Skip if we've already seen this URL
        if url in seen_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            continue
            
        seen_urls.add(url)
        new_article = {
            'email_uid': email.uid,
            'email_time': parse_date(email.date_str),
            'title': article['title'],
            'description': article['description'],
            'url': url,
            'created_at': datetime.now(),
            'source_domain': article.get('source_domain', ''),
            'raw_content': article.get('raw_content', ''),
        }
        new_articles.append(new_article)

    # Convert to DataFrame and handle duplicates with existing data
    new_df = pd.DataFrame(new_articles)
    
    if not existing_df.empty:
        # Remove any existing articles with same URLs (keep newest)
        existing_df = existing_df[~existing_df['url'].isin(new_df['url'])]
        df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        df = new_df

    # Save initial version
    storage.store_data(df, filepath, content_type='application/parquet')
    logger.info(f"Initial save: {len(new_articles)} articles from email {email.subject}")
    return new_articles

def sanitize_content(articles: List[dict]):
    """
    Sanitize content using OpenAI processing and update storage.
    """
    # Define the current date internally within the function
    current_date = datetime.now().strftime('%Y-%m-%d')
    raw_contents = [article['raw_content'] for article in articles]
    sanitizer = ContentSanitizer()

    logger.info(f"Sanitizing {len(raw_contents)} items")

    sanitized_contents = sanitizer.sanitize_contents(raw_contents)

    # Update DataFrame with sanitized contents using URL matching
    storage = StorageUtil()
    filepath = f'newsletter-digest/{current_date}.parquet'

    try:
        df = pd.DataFrame(storage.read_data(filepath))
        for i, content in enumerate(sanitized_contents):
            url = articles[i]['url']  # Use the original articles list to get the URL
            df.loc[df['url'] == url, 'raw_content'] = content

        # Save updated version
        storage.store_data(df, filepath, content_type='application/parquet')
        logger.info("Sanitized content updated successfully.")
    except Exception as e:
        logger.error(f"Failed to update sanitized content: {str(e)}")


if __name__ == "__main__":
    fetch_unread_emails()
