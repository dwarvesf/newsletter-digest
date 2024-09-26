"""
This module is responsible for connecting to the email server, fetching unread emails,
processing them, and saving the processed content to the PostgreSQL database.
"""

import os
from imap_tools import MailBox, AND, OR, MailMessageFlags
from datetime import datetime, timedelta
from config_manager import get_allowed_senders
import logging
import socket
from email_parser import extract_articles, parse_date
from dotenv import load_dotenv
from database import get_db, save_article, get_articles
from sqlalchemy.orm import Session
import ast

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
    processes them, and saves the processed content to the PostgreSQL database.
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
    Processes a single email, extracts articles, and saves them to the PostgreSQL database.
    """
    # Extract articles from email
    articles = extract_articles(email)

    # Save articles to database
    db = next(get_db())
    for article in articles:
        save_article(
            db,
            email_uid=email.uid,
            email_time=parse_date(email.date_str),
            title=article['title'],
            description=article['description'],
            url=article['url'].split('?')[0],
            criteria=article['criteria']
        )
    
    logger.info(f"Processed and saved email: {email.subject}")

def fetch_articles_from_days(days):
    """
    Fetch articles from the last 'days' days from the PostgreSQL database.
    Returns a list of articles with properly parsed criteria.
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    logger.info(f"Fetching articles since {cutoff_date}")

    db = next(get_db())
    articles = get_articles(db, date_from=cutoff_date)

    # Parse criteria if needed
    for article in articles:
        if isinstance(article.criteria, str):
            try:
                article.criteria = ast.literal_eval(article.criteria)
            except (ValueError, SyntaxError):
                article.criteria = []  # Set to empty list if parsing fails

    return articles

if __name__ == "__main__":
    fetch_unread_emails()
