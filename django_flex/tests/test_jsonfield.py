"""
Tests for JSONField support in django_flex.
"""

import pytest

from django_flex.fields import get_json_fields, is_json_field_path
from django_flex.filters import parse_filter_key
from django_flex.response import get_field_value, build_nested_response


class TestGetJsonFields:
    """Tests for get_json_fields function."""

    @pytest.mark.django_db
    def test_returns_json_field_names(self):
        from app.models import Customer

        json_fields = get_json_fields(Customer)
        assert "metadata" in json_fields

    @pytest.mark.django_db
    def test_excludes_non_json_fields(self):
        from app.models import Customer

        json_fields = get_json_fields(Customer)
        assert "name" not in json_fields
        assert "email" not in json_fields


class TestIsJsonFieldPath:
    """Tests for is_json_field_path function."""

    @pytest.mark.django_db
    def test_detects_json_field_nested_path(self):
        from app.models import Customer

        is_json, field_name, key_path = is_json_field_path(Customer, "metadata.settings.theme")
        assert is_json is True
        assert field_name == "metadata"
        assert key_path == "settings.theme"

    @pytest.mark.django_db
    def test_detects_json_field_base_path(self):
        from app.models import Customer

        is_json, field_name, key_path = is_json_field_path(Customer, "metadata")
        assert is_json is True
        assert field_name == "metadata"
        assert key_path is None

    @pytest.mark.django_db
    def test_non_json_field(self):
        from app.models import Customer

        is_json, field_name, key_path = is_json_field_path(Customer, "company.name")
        assert is_json is False
        assert field_name is None
        assert key_path is None


class TestJsonFilters:
    """Tests for JSONField filtering via parse_filter_key."""

    def test_json_nested_key(self):
        field, op = parse_filter_key("metadata.settings.theme")
        assert field == "metadata__settings__theme"
        assert op is None

    def test_json_with_operator(self):
        field, op = parse_filter_key("metadata.count.gte")
        assert field == "metadata__count"
        assert op == "gte"

    def test_json_icontains(self):
        field, op = parse_filter_key("metadata.tags.icontains")
        assert field == "metadata__tags"
        assert op == "icontains"


class TestJsonFieldValue:
    """Tests for get_field_value with JSONFields."""

    @pytest.mark.django_db
    def test_extracts_nested_json_value(self):
        from app.models import Customer, Company, User

        # Create test user and company
        user = User.objects.create_user(username="test@example.com", email="test@example.com", password="TestPass123!")
        company = Company.objects.create(name="Test Co")

        # Create customer with JSON metadata
        customer = Customer.objects.create(
            company=company, name="John Doe", metadata={"settings": {"theme": "dark", "lang": "en"}, "tags": ["vip", "active"]}
        )

        # Test extraction with json_fields parameter
        value = get_field_value(customer, "metadata.settings.theme", {"metadata"})
        assert value == "dark"

    @pytest.mark.django_db
    def test_extracts_entire_json_field(self):
        from app.models import Customer, Company, User

        user = User.objects.create_user(username="test2@example.com", email="test2@example.com", password="TestPass123!")
        company = Company.objects.create(name="Test Co 2")

        customer = Customer.objects.create(company=company, name="Jane Doe", metadata={"key": "value"})

        value = get_field_value(customer, "metadata", {"metadata"})
        assert value == {"key": "value"}

    @pytest.mark.django_db
    def test_returns_none_for_missing_json_key(self):
        from app.models import Customer, Company, User

        user = User.objects.create_user(username="test3@example.com", email="test3@example.com", password="TestPass123!")
        company = Company.objects.create(name="Test Co 3")

        customer = Customer.objects.create(company=company, name="Bob Doe", metadata={"settings": {"theme": "light"}})

        value = get_field_value(customer, "metadata.settings.nonexistent", {"metadata"})
        assert value is None


class TestBuildNestedResponseWithJson:
    """Tests for build_nested_response with JSONFields."""

    @pytest.mark.django_db
    def test_builds_response_with_json_fields(self):
        from app.models import Customer, Company, User

        user = User.objects.create_user(username="test4@example.com", email="test4@example.com", password="TestPass123!")
        company = Company.objects.create(name="Test Co 4")

        customer = Customer.objects.create(company=company, name="Alice", metadata={"level": "gold", "prefs": {"notify": True}})

        response = build_nested_response(customer, ["name", "metadata.level", "metadata.prefs.notify"], {"metadata"})

        assert response["name"] == "Alice"
        assert response["metadata"]["level"] == "gold"
        assert response["metadata"]["prefs"]["notify"] is True
