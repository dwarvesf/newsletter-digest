import json
import logging
import argparse
from content_sanitizer import ContentSanitizer

logger = logging.getLogger(__name__)

# Parse batch_id from terminal arguments
parser = argparse.ArgumentParser(description="Process batch content sanitization.")
parser.add_argument("batch_id", type=str, help="The batch ID to process.")
args = parser.parse_args()
batch_id = args.batch_id

print(f"Starting batch content sanitization process for batch_id: {batch_id}")

sanitizer = ContentSanitizer()

# Check batch status
status = sanitizer._check_batch_status(batch_id=batch_id)
logger.info(f"Batch status: {status.status}")

# Retrieve output
output_file_id = status.output_file_id
if not output_file_id:
    logger.warning("No output file available.")
else:
    # Get file content using the correct API - synchronous in Python
    file_response = sanitizer.client.files.content(output_file_id)
    file_contents = file_response.text

    # Save batch file to file system
    batch_filename = f"{batch_id}_batch_file.jsonl"
    with open(batch_filename, "w") as batch_file:
        batch_file.write(file_contents)
    print(f"Batch file saved as {batch_filename}")

    # Save the entire file contents to the file system
    file_save_path = f"batch_files/{batch_id}_file_contents.jsonl"
    with open(file_save_path, "w") as file:
        file.write(file_contents)
    print(f"File contents saved to {file_save_path}")

