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
    - Provide the expanded queries in a JSON format, with the original query as the key. DO NOT include characters like ```json. Return the pure JSON as text.

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
