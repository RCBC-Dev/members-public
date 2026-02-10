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

import os

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "project.settings.test"
)  # or production

print("Starting serve.py")
from waitress import serve
from project.wsgi import application

print("Imported application")

if __name__ == "__main__":
    port = int(os.environ.get("HTTP_PLATFORM_PORT", 8000))
    print(f"Serving on port {port}")
    serve(application, host="0.0.0.0", port=port)
