from typing import List, Dict
import json
from pathlib import Path
import time
import logging
from openai import OpenAI
from datetime import datetime
import os
from config_manager import get_openai_model_name

logger = logging.getLogger(__name__)

check_interval = 60  # seconds
timeout_duration = 86400  # seconds (24 hours)

class BatchContentSanitizer:
    def __init__(self, api_key: str = None, model: str = None):
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.model = model or get_openai_model_name()
        self.system_prompt = (
            "You are a content cleaner. Clean and format the following markdown article. "
            "Remove any of the following:\n"
            "- Irrelevant links (e.g. unrelated URLs, 'read more', 'source' mentions)\n"
            "- HTML tags, code artifacts, or leftover formatting symbols\n"
            "- Unrelated or broken data from crawling\n"
            "- Repeated or redundant phrases\n"
            "Preserve the original content structure and meaning. Output clean, readable paragraphs."
        )
        self.batch_dir = Path("batch_files")
        self.batch_dir.mkdir(exist_ok=True)

    def _create_batch_file(self, contents: List[str]) -> Path:
        """Create JSONL file for batch processing"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jsonl_path = self.batch_dir / f"batch_input_{timestamp}.jsonl"
        
        try:
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for i, content in enumerate(contents):
                    json.dump({
                        "custom_id": f"content_{timestamp}_{i}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": self.model,    
                            "messages": [
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": content}
                            ],
                            "temperature": 0.1
                        }
                    }, f)
                    f.write("\n")
            
            logger.info(f"Created JSONL file: {jsonl_path}")
            return jsonl_path
            
        except Exception as e:
            logger.error(f"Error creating batch file: {str(e)}")
            if jsonl_path.exists():
                jsonl_path.unlink()
            raise

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
            input_file_id= file_id,
            endpoint= "/v1/chat/completions",
            completion_window= "24h"
        )
        logger.info(f"Created batch job: {batch.id}")
        return batch

    def _check_batch_status(self, batch_id: str) -> Dict:
        """Check status of batch job"""
        return self.client.batches.retrieve(batch_id)

    def _cleanup_file(self, file_path: Path):
        """Clean up batch file"""
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {str(e)}")

    def sanitize_contents(self, contents: List[str], batch_size: int = 20) -> List[str]:
        """Sanitize contents using batch processing"""
        batch_file = None
        try:
            # Create batch file
            batch_file = self._create_batch_file(contents)
            
            # Process batch
            jsonl_path = batch_file
            file_id = self._upload_file(jsonl_path)
            batch = self._create_batch_job(file_id)
            start_time = time.time()

            # Poll status
            while True:
                status = self._check_batch_status(batch.id)
                logger.info(f"Batch status: {status.status}")

                if status.status == "completed":
                    break
                elif status.status == "failed":
                    raise Exception(f"Batch job failed: {getattr(status, 'errors', 'Unknown error')}")

                if time.time() - start_time > timeout_duration:
                    logger.error("Batch job timed out.")
                    raise TimeoutError("Batch job timed out after 24 hours.")

                time.sleep(check_interval)

            # Retrieve output
            output_file_id = status.output_file_id
            if not output_file_id:
                logger.warning("No output file available.")
                return contents

            # Get file content using the correct API - synchronous in Python
            file_response = self.client.files.content(output_file_id)
            file_contents = file_response.text
            
            # Initialize results with original contents as fallback
            results = contents.copy()
            
            # Parse results from JSONL content and maintain order
            for line in file_contents.splitlines():
                if line.strip():  # Skip empty lines
                    result = json.loads(line)
                    # Check for successful response and extract content
                    if (result.get("custom_id") and 
                        result.get("response") and 
                        result["response"].get("status_code") == 200 and 
                        result["response"].get("body", {}).get("choices")):
                        
                        # Extract index from custom_id (format: content_timestamp_index)
                        _, _, idx = result["custom_id"].split('_')
                        idx = int(idx)
                        
                        # Extract sanitized content
                        content = result["response"]["body"]["choices"][0]["message"]["content"]
                        
                        # Place content at correct index
                        if 0 <= idx < len(results):
                            results[idx] = content
                        else:
                            logger.warning(f"Invalid index {idx} from custom_id: {result['custom_id']}")
                    else:
                        logger.warning(f"Skipping invalid response: {line}")
            
            logger.info(f"Successfully processed {len(results)} content items")
            return results
            
        except Exception as e:
            logger.error(f"Batch processing error: {str(e)}")
            return contents
            
        finally:
            if batch_file:
                self._cleanup_file(batch_file)
