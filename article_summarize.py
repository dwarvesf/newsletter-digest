import requests
from bs4 import BeautifulSoup
from transformers import pipeline,T5Tokenizer, T5ForConditionalGeneration

# Remove non-ASCII characters and extra whitespace
def preprocess_text(text):
    clean_text = ''.join([char if char.isascii() else ' ' for char in text])
    clean_text = ' '.join(clean_text.split())  # Remove extra spaces
    return clean_text

# Function to fetch HTML content from a URL
def fetch_content(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching content from {url}: {e}")
        return None

# Function to extract main text content using BeautifulSoup
def extract_text(html_content):
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Extract text from <p> tags
        paragraphs = [p.get_text() for p in soup.find_all("p")]
        # Join paragraphs into a single text block
        return " ".join(paragraphs)
    except Exception as e:
        print(f"Error parsing HTML content: {e}")
        return None


def crawl_and_summarize(url):
    print(f"crawl_and_summarize URL: {url}")
    html_content = fetch_content(url)
    if html_content:
        text_content = extract_text(html_content)
        text_content = preprocess_text(text_content)
        if text_content:
            print("Extracted content. Starting summarization...")
            summary = summarize_text(text_content)
            return summary
        else:
            print("No text content found.")
    return None


def summarize_text(text, model_name='t5-base', max_input_length=512):
    """
    Summarize the input text using the HuggingFace transformer model (e.g., T5 or BART).
    """
    # Initialize tokenizer and model
    tokenizer = T5Tokenizer.from_pretrained(model_name,legacy=False)
    model = T5ForConditionalGeneration.from_pretrained(model_name)

    # Tokenize the input text
    inputs = tokenizer.encode("summarize: " + text, return_tensors="pt", truncation=True, max_length=max_input_length)

    # Generate summary
    summary_ids = model.generate(inputs, max_length=300, num_beams=4, early_stopping=True)
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)

    return summary