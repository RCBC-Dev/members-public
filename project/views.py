"""
Views for the Members Enquiries System project.
"""

import os
from django.conf import settings
from django.http import FileResponse, Http404
from django.views.static import serve
from django.contrib.auth.decorators import login_required

@login_required
def serve_media_file(request, path):
    """
    Serve media files even when DEBUG is False.
    This is not recommended for production use with high traffic,
    but works well for smaller applications.
    """
    # Construct the full path to the media file
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    
    # Check if the file exists
    if not os.path.exists(full_path):
        raise Http404("Media file does not exist")
    
    # Serve the file
    return serve(request, path, document_root=settings.MEDIA_ROOT)
