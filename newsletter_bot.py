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
