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
Tests for application/message_service.py
"""

import json
import pytest
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib import messages as django_messages

from application.message_service import (
    MessageService,
    add_success_message,
    add_error_message,
    add_warning_message,
    add_info_message,
    create_json_response,
)


def make_request():
    """Create a request with a message storage backend attached."""
    factory = RequestFactory()
    request = factory.get("/")
    request.session = {}
    storage = FallbackStorage(request)
    request._messages = storage
    return request


def get_messages(request):
    """Return list of (level, message, tags) from the request's message storage."""
    return [(m.level, str(m), m.tags) for m in request._messages]


class TestMessageServiceAddMessage:
    """Tests for MessageService.add_message."""

    def test_adds_success_message(self):
        request = make_request()
        MessageService.add_message(request, "success", "It worked!")
        msgs = get_messages(request)
        assert len(msgs) == 1
        assert msgs[0][1] == "It worked!"
        assert msgs[0][0] == django_messages.SUCCESS

    def test_adds_error_message(self):
        request = make_request()
        MessageService.add_message(request, "error", "Something broke")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.ERROR

    def test_adds_warning_message(self):
        request = make_request()
        MessageService.add_message(request, "warning", "Watch out")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.WARNING

    def test_adds_info_message(self):
        request = make_request()
        MessageService.add_message(request, "info", "FYI")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.INFO

    def test_danger_maps_to_error(self):
        request = make_request()
        MessageService.add_message(request, "danger", "Danger!")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.ERROR

    def test_debug_maps_to_info(self):
        request = make_request()
        MessageService.add_message(request, "debug", "Debug info")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.INFO

    def test_unknown_type_defaults_to_info(self):
        request = make_request()
        MessageService.add_message(request, "nonsense", "Hello")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.INFO

    def test_normalized_type_is_in_tags(self):
        request = make_request()
        MessageService.add_message(request, "success", "Done")
        msgs = get_messages(request)
        assert "success" in msgs[0][2]


class TestMessageServiceConvenienceMethods:
    """Tests for the success/error/warning/info shortcut methods."""

    def test_success_method(self):
        request = make_request()
        MessageService.success(request, "All good")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.SUCCESS

    def test_error_method(self):
        request = make_request()
        MessageService.error(request, "Broken")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.ERROR

    def test_warning_method(self):
        request = make_request()
        MessageService.warning(request, "Careful")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.WARNING

    def test_info_method(self):
        request = make_request()
        MessageService.info(request, "Note")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.INFO


class TestMessageServiceJsonResponse:
    """Tests for MessageService.create_json_response."""

    def test_success_response_contains_success_true(self):
        response = MessageService.create_json_response(True, message="Done")
        data = json.loads(response.content)
        assert data["success"] is True

    def test_success_response_contains_message(self):
        response = MessageService.create_json_response(True, message="Created")
        data = json.loads(response.content)
        assert data["message"] == "Created"

    def test_success_response_message_type_is_success(self):
        response = MessageService.create_json_response(True, message="OK")
        data = json.loads(response.content)
        assert data["message_type"] == "success"

    def test_failure_response_contains_success_false(self):
        response = MessageService.create_json_response(False, error="Failed")
        data = json.loads(response.content)
        assert data["success"] is False

    def test_failure_response_contains_error(self):
        response = MessageService.create_json_response(False, error="Bad input")
        data = json.loads(response.content)
        assert data["error"] == "Bad input"

    def test_failure_response_uses_default_error_when_empty(self):
        response = MessageService.create_json_response(False)
        data = json.loads(response.content)
        assert data["error"] == "An error occurred"

    def test_success_response_merges_extra_data(self):
        response = MessageService.create_json_response(True, data={"id": 42})
        data = json.loads(response.content)
        assert data["id"] == 42

    def test_create_success_response_shortcut(self):
        response = MessageService.create_success_response("Saved")
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["message"] == "Saved"

    def test_create_error_response_shortcut(self):
        response = MessageService.create_error_response("Not found")
        data = json.loads(response.content)
        assert data["success"] is False
        assert data["error"] == "Not found"


class TestMessageServiceJavaScriptConfig:
    """Tests for MessageService.get_javascript_config."""

    def test_returns_message_types_key(self):
        config = MessageService.get_javascript_config()
        assert "message_types" in config

    def test_returns_default_options_key(self):
        config = MessageService.get_javascript_config()
        assert "default_options" in config

    def test_returns_type_config_key(self):
        config = MessageService.get_javascript_config()
        assert "type_config" in config

    def test_all_four_message_types_present(self):
        config = MessageService.get_javascript_config()
        for key in ["success", "error", "warning", "info"]:
            assert key in config["type_config"]


class TestBackwardCompatibilityFunctions:
    """Tests for the module-level backward compatibility functions."""

    def test_add_success_message(self):
        request = make_request()
        add_success_message(request, "OK")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.SUCCESS

    def test_add_error_message(self):
        request = make_request()
        add_error_message(request, "Fail")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.ERROR

    def test_add_warning_message(self):
        request = make_request()
        add_warning_message(request, "Watch")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.WARNING

    def test_add_info_message(self):
        request = make_request()
        add_info_message(request, "Note")
        msgs = get_messages(request)
        assert msgs[0][0] == django_messages.INFO

    def test_create_json_response_function(self):
        response = create_json_response(True, message="Done")
        data = json.loads(response.content)
        assert data["success"] is True
