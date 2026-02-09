"""
URL configuration for Members Enquiries System project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from .views import serve_media_file

urlpatterns = [
    # Admin URLs should be first to avoid being overridden
    path('admin/', admin.site.urls),

    # TinyMCE URLs for CSP-compliant rich text editing
    path('tinymce/', include('tinymce.urls')),

    # Microsoft Entra ID authentication URLs
    path('accounts/', include('allauth.urls')),

    # Main app URLs - keep this last to avoid conflicts
    path('', include('application.urls')),

    # Serve media files in all environments
    re_path(r'^media/(?P<path>.*)$', serve_media_file),
]

# Add debug toolbar in development
if settings.DEBUG:
    urlpatterns.append(path('__debug__/', include('debug_toolbar.urls')))
