from django.urls import path
from .views import UploadInitView, UploadCompleteView, LocalUploadView

app_name = 'api' # Using namespace to match reverse lookup in storage.py

urlpatterns = [
    path('init/', UploadInitView.as_view(), name='upload-init'),
    path('complete/', UploadCompleteView.as_view(), name='upload-complete'),
    path('local/<uuid:transaction_id>/', LocalUploadView.as_view(), name='local-upload'),
]
