# requirements.txt

```txt
imap-tools
beautifulsoup4
requests
python-dotenv
google-generativeai
numpy
sentence-transformers

```

# nlp_processor.py

```py
import logging
import numpy as np
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import time
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity

logger = logging.getLogger(__name__)

# Initialize the Gemini model
model = genai.GenerativeModel('gemini-1.5-pro')

# Initialize the sentence transformer model
sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

# List to store processed articles with their embeddings
processed_articles = []

def expand_queries(queries):
    """
    Expands multiple input queries using Gemini to include only the most relevant keywords,
    abbreviations, and core concepts directly related to each input.
    """
    prompt = f"""
    Expand each of the following queries into a concise set of the most relevant technical terms.
    For each query, focus only on:
    1. The exact input term
    2. Its most common abbreviations or alternative names
    3. Core concepts that are directly and strongly associated with the input

    Rules:
    - Limit the expansion of each query to a maximum of 5-7 terms
    - Include only technical terms directly related to each input
    - Exclude broader categories, related tools, or concepts that are not core to the input
    - Separate each term with a comma
    - Provide the expanded queries in a JSON format, with the original query as the key. DO NOT include characters like \`\`\`json. Return the pure JSON as text.

    Example output format:
    {{
        "React": "React, React.js, ReactJS, JSX, Virtual DOM",
        "Python": "Python, Py, CPython, PyPy, GIL, PEP"
    }}

    Queries to expand:
    {queries}

    Expanded queries:
    """
    
    response = model.generate_content(prompt)
    expanded_queries = response.text.strip()
    logger.info(f"Expanded queries: {expanded_queries}")
    
    try:
        import json
        expanded_dict = json.loads(expanded_queries)
        return {k: v.split(', ') for k, v in expanded_dict.items()}
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON response from Gemini")
        return {query: [query] for query in queries}

def get_embedding(text):
    """
    Get the embedding for a given text using sentence-transformers.
    """
    return sentence_model.encode(text)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def calculate_relevance(article, expanded_criteria):
    """
    Calculate relevance using a hybrid approach of embedding similarity and keyword matching.
    """
    logger.info(f"Calculating relevance for article: {article['title']}")
    
    # Embedding-based similarity
    article_embedding = get_embedding(f"{article['title']} {article['description']}")
    criteria_embedding = get_embedding(' '.join(expanded_criteria))
    embedding_similarity = cosine_similarity(article_embedding, criteria_embedding)
    
    # Keyword-based similarity
    article_text = f"{article['title']} {article['description']}".lower()
    keyword_similarity = 1.0 if any(term.lower() in article_text for term in expanded_criteria) else 0.0
    
    # Combine the two scores (you can adjust the weights as needed)
    relevance_score = 0.5 * embedding_similarity + 0.5 * keyword_similarity
    
    logger.info(f"Calculated relevance score: {relevance_score}")
    return relevance_score, article_embedding

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

def process_articles(articles, expanded_criteria):
    """
    Process articles, skipping duplicates and calculating relevance for unique articles.
    """
    unique_articles = []
    for article in articles:
        if not is_duplicate_article(article):
            relevance_score, article_embedding = calculate_relevance(article, expanded_criteria)
            article['relevance'] = relevance_score
            unique_articles.append(article)
        else:
            logger.info(f"Skipping duplicate article: {article['title']}")
    return unique_articles

# Clear the processed_articles list at the beginning of each run
def clear_processed_articles():
    global processed_articles
    processed_articles.clear()

```

# newsletter_bot.py

```py
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from email_crawler import fetch_emails
from email_parser import extract_content, clear_processed_articles as clear_parser_processed_articles
from nlp_processor import expand_queries, calculate_relevance
from config_manager import get_min_relevance_score, get_max_results, get_search_criteria
import google.generativeai as genai

# ANSI color codes
CYAN = "\033[96m"
RESET = "\033[0m"

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

logger = logging.getLogger(__name__)

def process_email(email):
    logger.info(f"Processing email: {email.subject}")
    return extract_content(email)

def process_emails():
    logger.info("Fetching and processing emails")
    emails = fetch_emails()
    all_articles = []
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_email = {executor.submit(process_email, email): email for email in emails}
        for future in as_completed(future_to_email):
            email = future_to_email[future]
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as exc:
                logger.error(f"Email processing generated an exception: {exc}")
    
    logger.info(f"Processed {len(all_articles)} unique articles from {len(emails)} emails")
    return all_articles

def apply_criteria(articles, criteria, expanded_criteria, used_articles):
    logger.info(f"Applying criteria: {criteria}")
    min_score = get_min_relevance_score()
    logger.info(f"Expanded criteria: {expanded_criteria}")
    
    relevant_articles = []
    for article in articles:
        if article['url'] in used_articles:
            continue
        
        relevance_score, article_embedding = calculate_relevance(article, expanded_criteria)
        
        if relevance_score >= min_score:
            logger.info(f"Article meets relevance criteria. Score: {relevance_score}")
            relevant_articles.append({
                'title': article['title'],
                'description': article['description'],
                'url': article['url'],
                'relevance_score': relevance_score
            })
        else:
            logger.info(f"Article does not meet relevance criteria. Score: {relevance_score}")
    
    return sorted(relevant_articles, key=lambda x: x['relevance_score'], reverse=True)

def generate_markdown_output(results_by_criteria):
    with open('newsletter_results.md', 'w') as f:
        for criteria, results in results_by_criteria.items():
            f.write(f"## {criteria}\n")
            f.write(f"Expanded keywords: {', '.join(results['expanded_criteria'])}\n")
            f.write("### Top articles\n")
            for article in results['articles']:
                f.write(f"#### [{article['title']}]({article['url']})\n")
                f.write(f"{article['description']}\n\n")
            f.write("\n")

if __name__ == "__main__":
    start_time = time.time()
    
    criteria_list = get_search_criteria()
    logger.info(f"Search criteria from config: {criteria_list}")
    
    # Clear processed articles set in email_parser
    clear_parser_processed_articles()
    
    # Expand all queries at once with tracking
    expanded_queries = expand_queries(criteria_list)
    logger.info(f"Expanded queries: {expanded_queries}")
    
    # Process emails once
    all_articles = process_emails()
    
    results_by_criteria = {}
    used_articles = set()
    max_results = get_max_results()
    
    for criteria in criteria_list:
        expanded_criteria = expanded_queries.get(criteria, [criteria])
        results = apply_criteria(all_articles, criteria, expanded_criteria, used_articles)
        
        selected_articles = results[:max_results]
        used_articles.update(article['url'] for article in selected_articles)
        
        results_by_criteria[criteria] = {
            'expanded_criteria': expanded_criteria,
            'articles': selected_articles
        }
    
    generate_markdown_output(results_by_criteria)
    logger.info("Results have been written to newsletter_results.md")
    
    end_time = time.time()
    total_execution_time = end_time - start_time
    
    print(f"Total execution time: {total_execution_time:.2f} seconds")
    print(f"Total unique articles processed: {len(all_articles)}")
    print(f"Total unique articles selected: {len(used_articles)}")

```

# email_parser.py

```py
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

```

# email_crawler.py

```py
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

```

# config_manager.py

```py
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

def get_search_days():
    # Retrieve the number of days to search for emails
    config = load_config()
    return config['search_settings']['default_days']

def get_min_relevance_score():
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

```

# config.yaml

```yaml
# File: config.yaml
# Responsibility: Storing configuration settings in a human-readable format
# This file contains:
# - Email settings (e.g., allowed senders)
# - Search settings (e.g., default number of days to search, minimum relevance score)
# - Output settings (e.g., maximum number of results to return)

email_settings:
  allowed_senders:
    - ngolap.nguyen@gmail.com
  allowed_domains:
    - tldrnewsletter.com

search_settings:
  default_days: 30
  min_relevance_score: 0.5
  criteria:
    - React
    - NextJS
    - Typescript
    - TailwindCSS
    - AI
    - Tools

output_settings:
  max_results: 10

```

# README.md

```md
# Newsletter Digest Bot

This project contains a bot that processes and digests newsletter content.

## Prerequisites

- Python 3.x
- pip (Python package installer)

## Setup

1. Clone this repository or download the source code.

2. Navigate to the project directory:

   \`\`\`
   cd /path/to/newsletter-digest
   \`\`\`

3. Create a virtual environment (optional but recommended):

   \`\`\`
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   \`\`\`

4. Install the required dependencies:

   \`\`\`
   pip install -r requirements.txt
   \`\`\`

5. Set up the configuration:
   - Ensure the `.env` file is present and contains the necessary environment variables.
   - Review and modify the `config.yaml` file if needed.

## Running the Bot

To run the newsletter digest bot, use the following command:

\`\`\`
python newsletter_bot.py
\`\`\`

## Configuration

- Environment variables are stored in the `.env` file.
- Additional configuration options can be found in `config.yaml`.

## Logging

The bot generates logs in the `newsletter_bot.log` file. Check this file for execution details and any issues.

## Project Structure

- `newsletter_bot.py`: Main entry point for the bot
- `config_manager.py`: Manages configuration loading
- `email_crawler.py`: Handles email retrieval
- `email_parser.py`: Parses email content
- `nlp_processor.py`: Processes text using NLP techniques

## Troubleshooting

If you encounter any issues, please check the following:

1. Ensure all dependencies are correctly installed.
2. Verify that the `.env` and `config.yaml` files are properly configured.
3. Check the `newsletter_bot.log` file for any error messages or warnings.

For further assistance, please contact the project maintainer.

```

# .gitignore

```
__pycache__
.obsidian
venv/*
newsletter_bot.log
newsletter_results.md

```

