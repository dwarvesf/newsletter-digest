"""
This module is responsible for connecting to the email server, fetching unread emails,
processing them, and saving the processed content using Google Cloud Storage.
"""

import os
from imap_tools import MailBox, AND, OR, MailMessageFlags
from datetime import datetime, timedelta
from config_manager import get_allowed_senders
import logging
import socket
from email_parser import extract_articles, parse_date
from dotenv import load_dotenv
from storage import StorageUtil
import ast
from typing import List, Optional
import pandas as pd

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
        with MailBox(imap_server, port=993).login(email, password) as mailbox:
            sender_filter = OR(*[f'FROM "{sender}"' for sender in allowed_senders])
            unread_filter = 'UNSEEN'
            
            logger.info("Applying filters and fetching emails")
            
            emails = list(mailbox.fetch(AND(sender_filter, unread_filter)))
            logger.info(f"Fetched {len(emails)} unread emails")

            # Sort emails by date (older to newer)
            emails.sort(key=lambda x: parse_date(x.date_str))
          
            print(f"Processing {len(emails)} emails")
            for email in emails:
                try:
                    process_and_save_email(email)
                    # Mark email as read if processing was successful
                    mailbox.flag(email.uid, MailMessageFlags.SEEN, True)
                except Exception as e:
                    logger.error(f"Failed to process email {email.subject}: {str(e)}")
                    # Ensure the email remains unread for the next fetch
                    mailbox.flag(email.uid, MailMessageFlags.SEEN, False)

    except socket.error as e:
        logger.error(f"Socket error: {str(e)}")
    except Exception as e:
        logger.error(f"Error connecting to email server: {str(e)}")

def process_and_save_email(email):
    """
    Processes a single email, extracts articles, and saves them to Parquet format.
    """
    # Extract articles from email
    articles = extract_articles(email)
    storage = StorageUtil()

    # Generate filepath with current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    filepath = f'newsletter-digest/{current_date}.parquet'

    # Get existing articles for today
    try:
        existing_df = pd.DataFrame(storage.read_data(filepath))
    except:
        existing_df = pd.DataFrame()

    # Prepare new articles
    new_articles = []
    for article in articles:
        new_article = {
            'email_uid': email.uid,
            'email_time': parse_date(email.date_str),
            'title': article['title'],
            'description': article['description'],
            'url': article['url'].split('?')[0],
            'criteria': str(article['criteria']),  # Convert list to string for Parquet
            'created_at': datetime.now(),
            'raw_content': article.get('raw_content', ''),
            'author': article.get('author', ''),
            'image_url': article.get('image_url', ''),
            'publish_date': article.get('publish_date', '')
        }
        new_articles.append(new_article)

    # Convert to DataFrame and combine with existing
    new_df = pd.DataFrame(new_articles)
    if not existing_df.empty:
        df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        df = new_df

    # Save as Parquet
    storage.store_data(df, filepath, content_type='application/parquet')
    logger.info(f"Processed and saved email: {email.subject} to {filepath}")

def fetch_articles_from_days(days: int, criteria: Optional[str] = None) -> List[dict]:
    """
    Fetch articles from the last 'days' days from Parquet files.
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    logger.info(f"Fetching articles since {cutoff_date}")

    storage = StorageUtil()
    all_articles = []

    # Generate list of dates to check
    dates_to_check = [
        (datetime.now() - timedelta(days=x)).strftime('%Y-%m-%d')
        for x in range(days)
    ]

    # Fetch and combine articles from each date
    for date_str in dates_to_check:
        try:
            filepath = f'newsletter-digest/{date_str}.parquet'
            df = pd.DataFrame(storage.read_data(filepath))
            if not df.empty:
                # Convert criteria string back to list
                df['criteria'] = df['criteria'].apply(ast.literal_eval)
                all_articles.append(df)
        except Exception as e:
            logger.debug(f"No articles found for {date_str}: {str(e)}")
            continue

    if not all_articles:
        return []

    # Combine all DataFrames
    combined_df = pd.concat(all_articles, ignore_index=True)
    
    # Filter by date
    mask = combined_df['email_time'] >= cutoff_date
    filtered_df = combined_df[mask]

    # Filter by criteria if provided
    if criteria:
        criteria_list = [c.strip().lower() for c in criteria.split(',')]
        mask = filtered_df['criteria'].apply(
            lambda x: any(c['name'].lower() in criteria_list for c in x)
        )
        filtered_df = filtered_df[mask]

    # Convert DataFrame back to list of dicts
    return filtered_df.to_dict('records')

if __name__ == "__main__":
    fetch_unread_emails()
