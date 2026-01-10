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
