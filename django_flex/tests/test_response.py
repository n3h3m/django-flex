"""
Tests for django_flex.response module.
"""

import pytest


class TestBuildNestedResponse:
    """Tests for build_nested_response function."""

    def test_none_object(self):
        from django_flex.response import build_nested_response

        result = build_nested_response(None, ["email"])
        assert result is None

    def test_simple_object(self):
        from django_flex.response import build_nested_response

        # Create a simple mock object
        class MockObj:
            id = 1
            name = "Test"
            email = "test@example.com"

        obj = MockObj()
        result = build_nested_response(obj, ["id", "name", "email"])

        assert result["id"] == 1
        assert result["name"] == "Test"
        assert result["email"] == "test@example.com"

    def test_nested_fields(self):
        from django_flex.response import build_nested_response

        # Create mock objects with nesting
        class MockCustomer:
            name = "Aisha Khan"
            email = "aisha@example.com"

        class MockBooking:
            id = 1
            status = "confirmed"
            customer = MockCustomer()

        obj = MockBooking()
        result = build_nested_response(obj, ["id", "status", "customer.name", "customer.email"])

        assert result["id"] == 1
        assert result["status"] == "confirmed"
        assert result["customer"]["name"] == "Aisha Khan"
        assert result["customer"]["email"] == "aisha@example.com"


class TestFlexResponse:
    """Tests for FlexResponse class."""

    def test_ok_response(self):
        from django_flex.response import FlexResponse

        response = FlexResponse.ok(id=1, name="Test")
        data = response.to_dict()

        assert data["id"] == 1
        assert data["name"] == "Test"

    def test_error_response(self):
        from django_flex.response import FlexResponse

        response = FlexResponse.error("NOT_FOUND", "Object not found")
        data = response.to_dict()

        assert data["error"] == "Object not found"

    def test_warning_response(self):
        from django_flex.response import FlexResponse

        response = FlexResponse.warning_response("LIMIT_CLAMPED", limit=200)
        data = response.to_dict()

        assert data["warning"] is True
        assert data["warning_code"] == "LIMIT_CLAMPED"
        assert data["limit"] == 200

    def test_ok_query_response(self):
        from django_flex.response import FlexResponse

        results = {"1": {"id": 1}, "2": {"id": 2}}
        pagination = {"offset": 0, "limit": 20, "has_more": False}
        response = FlexResponse.ok_query(results=results, pagination=pagination)
        data = response.to_dict()

        assert data["results"] == results
        assert data["pagination"] == pagination

    def test_http_status_codes(self):
        """Test that http_status returns correct status codes."""
        from django_flex.response import FlexResponse

        assert FlexResponse.ok().http_status == 200
        assert FlexResponse.ok_query(results={}).http_status == 200
        assert FlexResponse.error("NOT_FOUND").http_status == 404
        assert FlexResponse.error("PERMISSION_DENIED").http_status == 403
        assert FlexResponse.error("BAD_REQUEST").http_status == 400
        assert FlexResponse.error("UNAUTHORIZED").http_status == 401

    def test_to_dict_with_status_code(self):
        """Test that to_dict includes status_code when requested."""
        from django_flex.response import FlexResponse

        response = FlexResponse.ok(name="Test")
        data = response.to_dict(include_status_code=True)
        assert data["status_code"] == 200
        assert data["name"] == "Test"

        error_response = FlexResponse.error("NOT_FOUND", "Not found")
        error_data = error_response.to_dict(include_status_code=True)
        assert error_data["status_code"] == 404
        assert error_data["error"] == "Not found"

    def test_to_dict_without_status_code(self):
        """Test that to_dict excludes status_code by default."""
        from django_flex.response import FlexResponse

        response = FlexResponse.ok(name="Test")
        data = response.to_dict()
        assert "status_code" not in data


class TestAlwaysHttp200:
    """Tests for ALWAYS_HTTP_200 setting."""

    def test_always_http_200_false_uses_real_status(self, settings):
        """When ALWAYS_HTTP_200=False, use real HTTP status codes."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": False}
        flex_settings.reload()

        response = FlexResponse.error("NOT_FOUND", "Not found")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert json_response.status_code == 404
        assert "status_code" not in data

    def test_always_http_200_true_returns_200(self, settings):
        """When ALWAYS_HTTP_200=True, return HTTP 200 with status_code in payload."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.error("NOT_FOUND", "Not found")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert json_response.status_code == 200
        assert data["status_code"] == 404
        assert data["error"] == "Not found"

        # Cleanup
        settings.DJANGO_FLEX = {}
        flex_settings.reload()

    def test_always_http_200_success_response(self, settings):
        """When ALWAYS_HTTP_200=True, success responses include success=True, no msg."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.ok(id=1, name="Test")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert json_response.status_code == 200
        assert data["status_code"] == 200
        assert data["success"] is True
        assert "msg" not in data  # No msg for success responses
        assert data["id"] == 1

        # Cleanup
        settings.DJANGO_FLEX = {}
        flex_settings.reload()

    def test_always_http_200_error_includes_success_false(self, settings):
        """When ALWAYS_HTTP_200=True, error responses include success=False and error."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.error("NOT_FOUND", "Object not found")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert json_response.status_code == 200
        assert data["status_code"] == 404
        assert data["success"] is False
        assert data["error"] == "Object not found"

        # Cleanup
        settings.DJANGO_FLEX = {}
        flex_settings.reload()

    def test_always_http_200_error_default_message(self, settings):
        """When ALWAYS_HTTP_200=True, error without message gets default from MSG_MAP."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.error("PERMISSION_DENIED")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert data["success"] is False
        assert data["error"] == "Permission denied"

        # Cleanup
        settings.DJANGO_FLEX = {}
        flex_settings.reload()

    def test_always_http_200_warning_response(self, settings):
        """When ALWAYS_HTTP_200=True, warning responses include warning field."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.warning_response("LIMIT_CLAMPED", limit=200)
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert data["success"] is True
        assert data["warning"] == "Limit was clamped to maximum allowed"
        assert data["limit"] == 200

        # Cleanup
        settings.DJANGO_FLEX = {}
        flex_settings.reload()


class TestDebugModeResponses:
    """Tests for DEBUG mode specific response behaviors."""

    def test_internal_error_includes_exception_in_debug(self, settings):
        """When DEBUG=True and ALWAYS_HTTP_200=True, internal errors include exception."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DEBUG = True
        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.error("INTERNAL_ERROR", "Traceback: ValueError at line 42")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert data["success"] is False
        assert data["status_code"] == 500
        assert data["error"] == "Traceback: ValueError at line 42"
        assert "exception" in data
        assert data["exception"] == "Traceback: ValueError at line 42"

        # Cleanup
        settings.DJANGO_FLEX = {}
        flex_settings.reload()

    def test_internal_error_excludes_exception_in_non_debug(self, settings):
        """When DEBUG=False, internal errors should NOT expose exception details."""
        import json
        from django_flex.response import FlexResponse
        from django_flex.conf import flex_settings

        settings.DEBUG = False
        settings.DJANGO_FLEX = {"ALWAYS_HTTP_200": True}
        flex_settings.reload()

        response = FlexResponse.error("INTERNAL_ERROR", "Sensitive traceback info")
        json_response = response.to_json_response()
        data = json.loads(json_response.content)

        assert data["success"] is False
        assert "exception" not in data

        # Cleanup
        settings.DJANGO_FLEX = {}
        settings.DEBUG = True
        flex_settings.reload()
