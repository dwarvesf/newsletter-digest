import os
import json
import base64
import pandas as pd
import io
from google.cloud import storage
from google.oauth2 import service_account
import hvac
import logging

logger = logging.getLogger(__name__)

class StorageUtil:
    def __init__(self):
        self.bucket_name = "df-landing-zone"
        self.vault_client = self._init_vault_client()
        self.gcs_client = self._init_gcs_client()

    def _init_vault_client(self):
        vault_token = os.getenv('VAULT_TOKEN')
        vault_url = os.getenv('VAULT_ADDR')
        vault_path = os.getenv('VAULT_PATH')

        client = hvac.Client(
            url=vault_url,
            token=vault_token
        )
        return client

    def _init_gcs_client(self):
        # Get GCP credentials from Vault
        secret = self.vault_client.read(os.getenv('VAULT_PATH'))
        gcp_creds = secret['data']['data']['GCP_SERVICE_ACCOUNT']

        try:
            decoded_creds = base64.b64decode(gcp_creds)
        except:
            decoded_creds = gcp_creds.encode()

        creds_dict = json.loads(decoded_creds)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        
        return storage.Client(credentials=credentials)

    def store_data(self, data, filepath, content_type='application/json'):
        """
        Store data in Google Cloud Storage
        
        Args:
            data: Data to store (dict, list, or pandas DataFrame)
            filepath: Path in bucket where to store the file
            content_type: Content type of the file (default: application/json)
        """
        print(f"Storing data to {filepath}")

        bucket = self.gcs_client.bucket(self.bucket_name)
        blob = bucket.blob(filepath)
        if isinstance(data, pd.DataFrame):
            buffer = io.BytesIO()
            data.to_parquet(buffer)
            blob.upload_from_string(buffer.getvalue(), content_type='application/parquet')
        elif isinstance(data, (dict, list)):
            data = json.dumps(data)
            blob.upload_from_string(data, content_type=content_type)
        else:
            raise ValueError("Unsupported data type for storage")
        
        return f"gs://{self.bucket_name}/{filepath}"

    def read_data(self, filepath):
        """
        Read data from Google Cloud Storage
        
        Args:
            filepath: Path in bucket where the file is stored
        """
        bucket = self.gcs_client.bucket(self.bucket_name)
        blob = bucket.blob(filepath)
        
        content = blob.download_as_string()
        try:
            buffer = io.BytesIO(content)
            return pd.read_parquet(buffer)
        except Exception:
            try:
                return json.loads(content)
            except:
                return content.decode()

    def list_blobs(self, prefix=None):
        """
        List all blobs in the bucket with optional prefix filter
        
        Args:
            prefix: Optional prefix to filter blobs (e.g., 'articles/')
            
        Returns:
            List of dictionaries containing blob info (name, size, updated)
        """
        bucket = self.gcs_client.bucket(self.bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        
        blob_list = []
        for blob in blobs:
            blob_list.append({
                'name': blob.name,
                'size': f"{blob.size/1024:.2f} KB",
                'updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),
                'content_type': blob.content_type
            })
        
        return blob_list

    def inspect_data(self, filepath):
        """
        Read and preview data from a specific file
        
        Args:
            filepath: Path to the file in the bucket
            
        Returns:
            Dictionary with file metadata and content preview
        """
        bucket = self.gcs_client.bucket(self.bucket_name)
        blob = bucket.blob(filepath)
        
        if not blob.exists():
            return {'error': 'File not found'}
        
        content = blob.download_as_string()
        try:
            buffer = io.BytesIO(content)
            parsed_content = pd.read_parquet(buffer)
            preview = {
                'total_items': len(parsed_content),
                'first_item': parsed_content.iloc[0].to_dict() if not parsed_content.empty else None,
                'last_updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),
                'size': f"{blob.size/1024:.2f} KB"
            }
        except Exception:
            try:
                parsed_content = json.loads(content)
                if isinstance(parsed_content, list):
                    preview = {
                        'total_items': len(parsed_content),
                        'first_item': parsed_content[0] if parsed_content else None,
                        'last_updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),
                        'size': f"{blob.size/1024:.2f} KB"
                    }
                else:
                    preview = {
                        'content_type': 'json',
                        'data': parsed_content,
                        'last_updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),
                        'size': f"{blob.size/1024:.2f} KB"
                    }
            except json.JSONDecodeError:
                preview = {
                    'content_type': 'text',
                    'preview': content.decode()[:200] + '...',
                    'last_updated': blob.updated.strftime('%Y-%m-%d %H:%M:%S'),
                    'size': f"{blob.size/1024:.2f} KB"
                }
        
        return preview

    def delete_data(self, filepath):
        """
        Delete a file from Google Cloud Storage
        
        Args:
            filepath: Path to the file in the bucket
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob(filepath)
            
            if not blob.exists():
                logger.warning(f"File not found: {filepath}")
                return False
            
            blob.delete()
            logger.info(f"Successfully deleted: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {str(e)}")
            return False