"""
This module is responsible for loading and managing the application's configuration.
It reads the YAML config file and provides functions to access specific configuration values.
It also includes validation for the allowed senders list.
"""

import yaml
import re
import logging

logger = logging.getLogger(__name__)

def load_config():
    # Load the YAML configuration file
    with open('config.yaml', 'r') as file:
        return yaml.safe_load(file)

def validate_email(email):
    # Validate if a string is a valid email address
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

def validate_domain(domain):
    # Validate if a string is a valid domain
    return re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain) is not None

def get_allowed_senders():
    # Retrieve and validate the list of allowed senders and domains from the config
    config = load_config()
    allowed_senders = config['email_settings']['allowed_senders']
    allowed_domains = config['email_settings'].get('allowed_domains', [])
    
    valid_senders = [sender for sender in allowed_senders if validate_email(sender)]
    valid_domains = [domain for domain in allowed_domains if validate_domain(domain)]
    
    invalid_senders = set(allowed_senders) - set(valid_senders)
    invalid_domains = set(allowed_domains) - set(valid_domains)
    
    if invalid_senders:
        logger.warning(f"Invalid senders in config: {', '.join(invalid_senders)}")
    if invalid_domains:
        logger.warning(f"Invalid domains in config: {', '.join(invalid_domains)}")
    
    return valid_senders + [f"*@{domain}" for domain in valid_domains]

def get_min_relevancy_score():
    # Retrieve the minimum relevance score for articles
    config = load_config()
    return config['search_settings']['min_relevance_score']

def get_max_results():
    # Retrieve the maximum number of results to display
    config = load_config()
    return config['output_settings']['max_results']

def get_search_criteria():
    # Retrieve the list of search criteria from the config
    config = load_config()
    return config['search_settings']['criteria']

def get_cron_frequency():
    # Retrieve the frequency for the cron job in minutes
    config = load_config()
    return config['cron_settings']['frequency']

def get_openai_rate_limit():
    # Retrieve the OpenAI API rate limit from the config
    config = load_config()
    return config['api_settings']['openai_rate_limit']

def get_openai_model_name():
    # Retrieve the OpenAI model name from the config
    config = load_config()
    return config['api_settings']['openai_model_name']
