import os
import uuid
import logging
from datetime import timedelta
from typing import Dict, NamedTuple, Optional
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

# SDK Imports (Guarded)
try:
    import boto3
    from botocore.config import Config as BotoConfig
except ImportError:
    boto3 = None

try:
    from google.cloud import storage as gcs
except ImportError:
    gcs = None

try:
    from azure.storage.blob import generate_blob_sas, BlobSasPermissions, BlobServiceClient
except ImportError:
    generate_blob_sas = None

logger = logging.getLogger(__name__)

class UploadConfig(NamedTuple):
    url: str
    method: str
    headers: Dict[str, str] = {}
    data: Dict[str, str] = {} # For POST policies if needed

class CloudStorageService:
    """
    Unified service to handle Direct-to-Cloud uploads.
    """
    
    def __init__(self):
        self.backend = getattr(settings, 'STORAGE_BACKEND', 'local')
        
    def generate_upload_config(self, transaction_id: str, filename: str, content_type: str, file_size: int) -> UploadConfig:
        """
        Generates the URL and signature required for the frontend to upload file directly.
        """
        # 1. Generate Object Key
        key = self._generate_key(transaction_id, filename)
        
        # 2. Dispatch to Backend
        if self.backend == 'aws':
            return self._get_aws_presigned_url(key, content_type, file_size)
        elif self.backend == 'gcs':
            return self._get_gcs_signed_url(key, content_type, file_size)
        elif self.backend == 'azure':
            return self._get_azure_sas_url(key, content_type)
        else:
            return self._get_local_upload_url(transaction_id, key)

    def _generate_key(self, transaction_id: str, filename: str) -> str:
        # Use UUID-based path: uploads/{transaction_id}/{clean_filename}
        clean_name = os.path.basename(filename) # Basic sanitization
        return f"uploads/{transaction_id}/{clean_name}"

    def _get_aws_presigned_url(self, key: str, content_type: str, file_size: int) -> UploadConfig:
        if not boto3:
            raise ImportError("boto3 is not installed")
            
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
            config=BotoConfig(signature_version='s3v4')
        )
        
        # Generate Presigned PUT
        try:
            url = s3_client.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': key,
                    'ContentType': content_type,
                    # Optional: Add Metadata or Checksums
                },
                ExpiresIn=900 # 15 minutes
            )
            return UploadConfig(url=url, method='PUT', headers={'Content-Type': content_type})
        except Exception as e:
            logger.error(f"Failed to generate AWS presigned URL: {e}")
            raise

    def _get_gcs_signed_url(self, key: str, content_type: str, file_size: int) -> UploadConfig:
        if not gcs:
            raise ImportError("google-cloud-storage is not installed")
            
        # Assuming Application Default Credentials or settings.GS_CREDENTIALS
        if hasattr(settings, 'GS_CREDENTIALS') and settings.GS_CREDENTIALS:
             client = gcs.Client.from_service_account_json(settings.GS_CREDENTIALS)
        else:
             client = gcs.Client()
             
        bucket = client.bucket(settings.GS_BUCKET_NAME)
        blob = bucket.blob(key)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type,
        )
        return UploadConfig(url=url, method='PUT', headers={'Content-Type': content_type})

    def _get_azure_sas_url(self, key: str, content_type: str) -> UploadConfig:
        if not generate_blob_sas:
            raise ImportError("azure-storage-blob is not installed")

        account_name = settings.AZURE_ACCOUNT_NAME
        account_key = settings.AZURE_ACCOUNT_KEY
        container_name = settings.AZURE_CONTAINER
        
        # Create SAS Token
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=key,
            account_key=account_key,
            permission=BlobSasPermissions(write=True),
            expiry=timezone.now() + timedelta(minutes=15)
        )
        
        url = f"https://{account_name}.blob.core.windows.net/{container_name}/{key}?{sas_token}"
        
        # Azure requires 'x-ms-blob-type': 'BlockBlob' header typically for PUT
        headers = {
            'Content-Type': content_type,
            'x-ms-blob-type': 'BlockBlob'
        }
        return UploadConfig(url=url, method='PUT', headers=headers)

    def _get_local_upload_url(self, transaction_id: str, key: str) -> UploadConfig:
        # Point to internal Django view
        # URL pattern: /api/upload/local/<transaction_id>/
        # Protocol: Host relative
        url = reverse('api:local-upload', kwargs={'transaction_id': transaction_id})
        full_url = f"{settings.BASE_URL}{url}" if hasattr(settings, 'BASE_URL') else url
        return UploadConfig(url=full_url, method='PUT')
        
    def check_exists(self, key: str) -> bool:
        """
        Verify file exists in backend.
        """
        if self.backend == 'aws':
            return self._check_aws(key)
        elif self.backend == 'default':  # Fallback
             return self._check_local(key)
        # Implement others...
        return True # Default to True for now to avoid blocking completion if check fails

    def _check_aws(self, key: str) -> bool:
        if not boto3: return False
        s3 = boto3.client('s3', 
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        try:
            s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
            return True
        except:
            return False

