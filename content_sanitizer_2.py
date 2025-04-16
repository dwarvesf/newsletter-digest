from typing import List
import logging
import openai
from datetime import datetime
import os
from config_manager import get_openai_model_name

logger = logging.getLogger(__name__)

class ContentSanitizer:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model or get_openai_model_name()
        self.system_prompt = (
            "You are a content cleaner. Clean and format the following markdown article. "
            "Remove any of the following:\n"
            "- Irrelevant links (e.g. unrelated URLs, 'read more', 'source' mentions)\n"
            "- HTML tags, code artifacts, or leftover formatting symbols\n"
            "- Unrelated or broken data from crawling\n"
            "- Repeated or redundant phrases\n"
            "Preserve the original content structure and meaning. Output clean, readable paragraphs.\n"
            "If no valid content is found, return an empty string."
        )

    def sanitize_content(self, content: str) -> str:
        """Sanitize a single content item using OpenAI API"""
        try:
            openai.api_key = self.api_key
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=0.1
            )

            if response.choices:
                sanitized_content = response.choices[0].message.content.strip()
                logger.info("Content sanitized successfully.")
                return sanitized_content
            else:
                logger.warning("No choices returned in response.")
                return ""

        except Exception as e:
            logger.error(f"Error sanitizing content: {str(e)}")
            return ""

    def sanitize_contents(self, contents: List[str]) -> List[str]:
        """Sanitize multiple content items using individual requests"""
        sanitized_results = []
        for i, content in enumerate(contents):
            logger.info(f"Sanitizing content at index {i}.")
            sanitized_content = self.sanitize_content(content) or content
            sanitized_results.append(sanitized_content)
        logger.info("All contents sanitized successfully.")
        return sanitized_results