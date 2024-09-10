"""
This module is responsible for connecting to the email server and fetching emails.
It uses the IMAP protocol to retrieve unread emails from allowed senders from the beginning of the current month.
"""

import os
from imap_tools import MailBox, OR, AND
from datetime import date
import calendar
from config_manager import get_allowed_senders
import logging
import socket

logger = logging.getLogger(__name__)

def create_sender_filter(allowed_senders):
    """
    Creates an IMAP filter for the allowed senders.
    It handles both full email addresses and domains.
    """
    full_emails = [sender for sender in allowed_senders if not sender.startswith('@')]
    domains = [sender[1:] for sender in allowed_senders if sender.startswith('@')]
    
    filters = []
    if full_emails:
        filters.append(OR(*[f'FROM "{email}"' for email in full_emails]))
    if domains:
        filters.append(OR(*[f'FROM "*@{domain}"' for domain in domains]))
    
    return OR(*filters) if len(filters) > 1 else filters[0]

def get_first_day_of_current_month():
    """
    Returns the first day of the current month as a string in the format 'DD-MMM-YYYY'.
    """
    today = date.today()
    first_day = date(today.year, today.month, 1)
    return first_day.strftime("%d-%b-%Y")

def fetch_emails():
    """
    Connects to the IMAP server and fetches unread emails from allowed senders from the beginning of the current month.
    """
    email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')
    imap_server = os.getenv('IMAP_SERVER')
    allowed_senders = get_allowed_senders()

    logger.info(f"Connecting to IMAP server: {imap_server}")
    logger.info("Fetching unread emails from the beginning of the current month")

    try:
        with MailBox(imap_server, port=993).login(email, password) as mailbox:
            sender_filter = create_sender_filter(allowed_senders)
            date_filter = f'SINCE {get_first_day_of_current_month()}'
            unread_filter = 'UNSEEN'
            
            logger.info("Applying filters and fetching emails")
            emails = list(mailbox.fetch(AND(sender_filter, date_filter, unread_filter)))
            logger.info(f"Fetched {len(emails)} unread emails")
            return emails
    except socket.error as e:
        logger.error(f"Socket error: {str(e)}")
    except Exception as e:
        logger.error(f"Error connecting to email server: {str(e)}")
    return []

if __name__ == "__main__":
    emails = fetch_emails()
    for email in emails:
        logger.info(f"From: {email.from_}, Subject: {email.subject}")
