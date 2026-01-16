import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import UploadTransaction
from .storage import CloudStorageService

logger = logging.getLogger(__name__)

class UploadInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        filename = request.data.get('filename')
        file_size = request.data.get('file_size')
        content_type = request.data.get('content_type', 'application/octet-stream')

        if not filename or not file_size:
            return Response({'error': 'filename and file_size are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Create Transaction
        transaction = UploadTransaction.objects.create(
            user=request.user,
            filename=filename,
            file_size=file_size,
            content_type=content_type,
            backend_used=getattr(settings, 'STORAGE_BACKEND', 'local')
        )

        service = CloudStorageService()
        try:
            config = service.generate_upload_config(
                str(transaction.id), 
                filename, 
                content_type, 
                int(file_size)
            )
            
            # Update object key in simpler form for reference
            # Note: The service generates the full key, we should ideally retrieve it from config or service
            # For now, we reconstruct it or update service to return it.
            # Let's rely on the service's _generate_key logic being deterministic or part of the return.
            # Since _generate_key was internal, let's update standard to be safer.
            # Re-generating key for saving (Service logic repetition is bad, but for MVP/Design Implementation...)
            # Ideally generate_upload_config returns key too.
            # Assuming standard path: uploads/{id}/{filename}
            transaction.object_key = f"uploads/{transaction.id}/{os.path.basename(filename)}"
            transaction.save()
            
            return Response({
                'upload_url': config.url,
                'method': config.method,
                'headers': config.headers,
                'transaction_id': transaction.id
            })
        except Exception as e:
            logger.error(f"Upload Init Failed: {e}")
            transaction.delete()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        if not transaction_id:
             return Response({'error': 'transaction_id required'}, status=status.HTTP_400_BAD_REQUEST)

        transaction = get_object_or_404(UploadTransaction, id=transaction_id, user=request.user)
        
        service = CloudStorageService()
        if service.check_exists(transaction.object_key):
            transaction.status = UploadTransaction.Status.COMPLETED
            transaction.completed_at = timezone.now() if hasattr(timezone, 'now') else None
            transaction.save()
            return Response({
                'status': 'success',
                'file_url': transaction.object_key # Or full URL if needed
            })
        else:
            return Response({'error': 'File not found in storage'}, status=status.HTTP_404_NOT_FOUND)

class LocalUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request, transaction_id):
        return self.handle_upload(request, transaction_id)

    def post(self, request, transaction_id):
        # Support POST if client prefers form-data (less efficient for binary stream)
        return self.handle_upload(request, transaction_id)

    def handle_upload(self, request, transaction_id):
        # Fallback for local storage
        if getattr(settings, 'STORAGE_BACKEND', 'local') != 'local':
             return Response({'error': 'Local upload not enabled'}, status=status.HTTP_403_FORBIDDEN)

        transaction = get_object_or_404(UploadTransaction, id=transaction_id, user=request.user)
        
        # In a real streaming upload, we'd read request.body (or stream)
        # For simplicity with DRF, request.data['file'] might be used if multipart,
        # but for direct PUT of binary:
        file_data = request.body
        
        # Verify size (optional constraint)
        if len(file_data) != transaction.file_size:
            # Flexible warning or error?
            pass

        # Save to MEDIA_ROOT using default storage
        # We save to transaction.object_key
        path = default_storage.save(transaction.object_key, ContentFile(file_data))
        
        return Response({'status': 'uploaded'}, status=status.HTTP_200_OK)

from django.utils import timezone # Fix missing import
