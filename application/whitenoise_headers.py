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

def add_cors_headers(headers, path, url):
    """
    Add CORS headers to static files for allowed origins only.
    """
    import os
    
    # Determine domain based on environment
    environment = os.environ.get('ENVIRONMENT', '').strip().lower()
    if environment == 'production':
        headers['Access-Control-Allow-Origin'] = 'https://membersenquiries.redclev.net'
    elif environment == 'test':
        headers['Access-Control-Allow-Origin'] = 'https://membersenquiries-test.redclev.net'
    else:
        # Fallback for test environment
        headers['Access-Control-Allow-Origin'] = 'https://membersenquiries-test.redclev.net'
    
    headers['Vary'] = 'Origin'