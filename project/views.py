# Copyright (C) 2026 Redcar & Cleveland Borough Council
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
