import argparse
from email_crawler import fetch_unread_emails

def main():
    parser = argparse.ArgumentParser(description="Newsletter Digest Service Runner")
    parser.add_argument('--crawl', action='store_true', help='Run the email crawler')
    
    args = parser.parse_args()
   
    elif args.crawl:
        print("Starting email crawler...")
        fetch_unread_emails()
    else:
        print("Please specify a service to run: --crawl")

if __name__ == "__main__":
    main()
