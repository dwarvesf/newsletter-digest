from typing import List, Dict
import json
from pathlib import Path
import time
import logging
from openai import OpenAI
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchContentSanitizer:
    def __init__(self, api_key: str = os.getenv('OPENAI_API_KEY'), model: str = get_openai_model_name()):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = (
            "You are a content cleaner. Clean and format the following markdown article. "
            "Remove any of the following:\n"
            "- Irrelevant links (e.g. unrelated URLs, 'read more', 'source' mentions)\n"
            "- HTML tags, code artifacts, or leftover formatting symbols\n"
            "- Unrelated or broken data from crawling\n"
            "- Repeated or redundant phrases\n"
            "Preserve the original content structure and meaning. Output clean, readable paragraphs."
        )

    def _create_batch_file(self, contents: List[str]) -> str:
        """Create JSONL file for batch processing"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsonl_path = f"batch_input_{timestamp}.jsonl"
        
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for content in contents:
                json.dump({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": content}
                    ],
                    "temperature": 0.1
                }, f)
                f.write("\n")
        
        logger.info(f"Created JSONL file: {jsonl_path}")
        return jsonl_path

    def _upload_file(self, file_path: str) -> str:
        """Upload JSONL file to OpenAI"""
        with open(file_path, "rb") as f:
            response = self.client.files.create(file=f, purpose="batch")
        file_id = response.id
        logger.info(f"Uploaded file with ID: {file_id}")
        return file_id

    def _create_batch_job(self, file_id: str) -> Dict:
        """Create batch processing job"""
        batch = self.client.batches.create(
            input_file=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        logger.info(f"Created batch job: {batch.id}")
        return batch

    def _check_batch_status(self, batch_id: str) -> Dict:
        """Check status of batch job"""
        return self.client.batches.retrieve(batch_id)

    def sanitize_contents(self, contents: List[str], check_interval: int = 300) -> List[str]:
        """
        Sanitize a list of contents using OpenAI's batch processing
        
        Args:
            contents: List of content strings to sanitize
            check_interval: Seconds between status checks
            
        Returns:
            List of sanitized content strings
        """
        try:
            # Create and upload batch file
            jsonl_path = self._create_batch_file(contents)
            file_id = self._upload_file(jsonl_path)
            
            # Create batch job
            batch = self._create_batch_job(file_id)
            
            # Monitor batch progress
            while True:
                status = self._check_batch_status(batch.id)
                if status.status == "completed":
                    break
                elif status.status == "failed":
                    raise Exception(f"Batch job failed: {status.error}")
                
                logger.info(f"Batch status: {status.status} ({status.progress_percent}%)")
                time.sleep(check_interval)
            
            # Get results
            results = []
            for output in status.output_files:
                with open(output.path, 'r') as f:
                    for line in f:
                        result = json.loads(line)
                        results.append(result['choices'][0]['message']['content'])
            
            # Cleanup
            Path(jsonl_path).unlink()
            
            return results
            
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}")
            return contents  # Return original content on error


