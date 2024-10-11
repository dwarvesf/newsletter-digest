# Newsletter Digest Bot

This project contains a bot that processes and digests newsletter content, focusing on specific topics of interest.

## Prerequisites

- Python 3.x
- pip (Python package installer)
- Docker (optional, for containerized deployment)

## Setup

1. Clone this repository or download the source code.

2. Navigate to the project directory:

   ```
   cd /path/to/newsletter-digest
   ```

3. Create a virtual environment (optional but recommended):

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

4. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

5. Set up the configuration:
   - Create a `.env` file and add the necessary environment variables, including the `GEMINI_API_KEY`.
   - Review and modify the `config.yaml` file to set up email settings, search criteria, and other configurations.

## Configuration

The `config.yaml` file contains important settings:

- Email settings (allowed senders and domains)
- Search settings (criteria, minimum relevance score)
- Output settings
- Cron job settings

Ensure these are correctly set up for your use case.

## Running the Bot

### Local Execution

To run the newsletter digest bot locally, use the following command:

```
python discord_bot.py
```

### Docker Execution

To run the bot using Docker:

1. Build the Docker image:

   ```
   docker build -t newsletter-digest-bot .
   ```

2. Run the Docker container:
   ```
   docker run -p 5000:5000 -p 80:80 newsletter-digest-bot
   ```

## Health Check

The application includes a health check endpoint at `/healthz`. You can access it at:

```
http://localhost:5000/healthz
```

This endpoint returns a JSON response `{"message": "ok"}` with a status code of 200 when the application is running correctly.

## Project Structure

- `discord_bot.py`: Main entry point for the bot
- `config_manager.py`: Manages configuration loading and validation
- `email_crawler.py`: Handles email retrieval (to be implemented)
- `email_parser.py`: Parses email content and processes articles

## Features

- Email parsing and content extraction
- Integration with Google's Gemini AI for content summarization
- Discord bot for displaying paginated article results
- Health check endpoint for monitoring application status

## Database Setup

This project uses PostgreSQL to store processed articles. Follow these steps to set up the database:

1. Install PostgreSQL on your system if you haven't already.
2. Create a new database for the project.
3. Update the `.env` file with your PostgreSQL connection details:
   ```
   DB_NAME=your_database_name
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=5432
   ```
4. The application will automatically create the necessary tables when it runs for the first time.

## Logging

The bot generates logs in the `newsletter_bot.log` file. Check this file for execution details and any issues.

## Troubleshooting

If you encounter any issues:

1. Ensure all dependencies are correctly installed.
2. Verify that the `.env` and `config.yaml` files are properly configured.
3. Check the `newsletter_bot.log` file for any error messages or warnings.
4. If using Docker, ensure the container is running and ports are correctly mapped.
5. Use the health check endpoint to verify the application's status.

For further assistance, please contact the project maintainer.
