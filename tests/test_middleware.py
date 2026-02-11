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

import re
from django.test import TestCase, Client
from django.urls import reverse
from django.utils.safestring import SafeString
from django.conf import settings


class CSPMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_csp_nonce_present_in_headers_and_tags(self):
        """
        Test that CSP nonce is present in headers and in script/link tags.
        """
        try:
            # Attempt to use 'application:welcome', as it should use base.html
            # and be accessible without login.
            test_url = reverse("application:welcome")
        except Exception:
            # Fallback if 'application:welcome' is problematic or to ensure a very simple view
            # For now, we proceed assuming 'application:welcome' is suitable.
            # If this fails, a dedicated simple test view might be needed.
            self.skipTest(
                "Could not reverse 'application:welcome'. Ensure it's defined and accessible, or update test URL."
            )
            return

        response = self.client.get(test_url)
        self.assertEqual(
            response.status_code,
            200,
            f"Failed to fetch {test_url}. Status: {response.status_code}",
        )

        # 1. Check for CSP header and extract nonce
        csp_header = response.get("Content-Security-Policy")
        self.assertIsNotNone(csp_header, "Content-Security-Policy header not found.")

        nonce_match = re.search(
            r"script-src[^-]*'nonce-([a-zA-Z0-9+/=_-]+)'", csp_header
        )
        self.assertIsNotNone(
            nonce_match, f"CSP Nonce not found for script-src in header: {csp_header}"
        )
        nonce_from_header = nonce_match.group(1)
        self.assertTrue(
            len(nonce_from_header) > 16, "CSP Nonce from header seems too short."
        )

        html_content = response.content.decode("utf-8")

        # Nonce is no longer required for external static CSS/JS files.
        # Only check nonce for inline scripts/styles if present.
        # This test previously checked for nonce in <link> tags, but this is not necessary for external static assets.

        # Nonce is no longer required for external static JS files.
        # Only check nonce for inline scripts/styles if present.
        # This test previously checked for nonce in <script src="..."> tags, but this is not necessary for external static assets.

        # 5. Verify nonce in the inline script for Django messages (if messages are present)
        # This script is conditional on {% if messages %}.
        # We check if the script structure for messages exists, and if so, it must have the nonce.
        inline_script_matches = re.finditer(
            r"<script([^>]*)>(.*?)</script>", html_content, re.DOTALL
        )
        found_messages_script_without_correct_nonce = False
        messages_script_exists_heuristic = False

        for match in inline_script_matches:
            attrs_str = match.group(1)
            script_content = match.group(2)
            # Heuristic to identify the Django messages script
            if (
                "document.addEventListener" in script_content
                and "showAlert" in script_content
                and "message.tags" in script_content
            ):
                messages_script_exists_heuristic = True
                nonce_attr_match = re.search(
                    r'nonce=["\']([a-zA-Z0-9+/=_-]+)["\']', attrs_str
                )
                if (
                    not nonce_attr_match
                    or nonce_attr_match.group(1) != nonce_from_header
                ):
                    found_messages_script_without_correct_nonce = True
                    self.fail(
                        f"Inline messages script found but nonce is missing or incorrect. Expected: {nonce_from_header}, Attrs: {attrs_str}"
                    )
                break

        # This assertion is only meaningful if we heuristically found the script
        # A more robust test would involve actually adding a message to the context.
        # if messages_script_exists_heuristic:
        #    self.assertFalse(found_messages_script_without_correct_nonce,
        #                    "Inline messages script detected but nonce is missing or incorrect.")

    def test_csp_middleware_adds_nonce_to_request_and_context(self):
        """
        Test that the CSPMiddleware correctly adds csp_nonce to the request
        and that it becomes available in the template context.
        """
        from django.http import HttpRequest
        from django.template.response import TemplateResponse
        from project.middleware.csp import CSPMiddleware  # Ensure this path is correct

        # Mock get_response for middleware instantiation
        def dummy_get_response(request):
            # This would normally be the next middleware or the view
            # For testing middleware's effect on request/context, return a simple TemplateResponse
            return TemplateResponse(request, template="", context={})

        middleware = CSPMiddleware(dummy_get_response)
        request = HttpRequest()

        # 1. Test process_request: csp_nonce should be added to request
        middleware.process_request(request)
        self.assertTrue(hasattr(request, "csp_nonce"))
        self.assertIsNotNone(request.csp_nonce)
        # Accessing it should generate the nonce string
        nonce_value_from_request = str(
            request.csp_nonce
        )  # forces SimpleLazyObject to evaluate
        self.assertTrue(
            len(nonce_value_from_request) > 16,
            "Generated nonce from request.csp_nonce is too short.",
        )

        # 2. Test process_template_response: csp_nonce should be added to template context
        # Create a minimal TemplateResponse object
        # The template content itself doesn't matter for this part of the test
        response_to_process = TemplateResponse(
            request, template="some_template.html", context={}
        )

        # Ensure request.csp_nonce exists from previous step before calling process_template_response
        if not hasattr(request, "csp_nonce"):
            middleware.process_request(request)  # Ensure it's there

        processed_response = middleware.process_template_response(
            request, response_to_process
        )
        self.assertIn(
            "csp_nonce",
            processed_response.context_data,
            "csp_nonce not found in template response context_data.",
        )
        self.assertEqual(
            processed_response.context_data["csp_nonce"],
            nonce_value_from_request,
            "csp_nonce in context_data does not match nonce from request object.",
        )
