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


def add_cors_headers(headers):
    """
    Add CORS headers to static files for allowed origins only.
    Uses the DOMAIN environment variable for the origin.
    """
    import os

    # Get domain from environment variable
    domain = os.environ.get("DOMAIN", "localhost")

    # Determine protocol based on environment
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    protocol = "https" if environment in ("production", "test") else "http"

    headers["Access-Control-Allow-Origin"] = f"{protocol}://{domain}"
    headers["Vary"] = "Origin"
