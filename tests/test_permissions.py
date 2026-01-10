"""
Tests for django_flex.permissions module.
"""

import pytest


class TestFieldMatchesPattern:
    """Tests for field_matches_pattern function."""

    def test_wildcard_matches_base_field(self):
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("name", "*") is True
        assert field_matches_pattern("email", "*") is True

    def test_wildcard_does_not_match_nested(self):
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("customer.name", "*") is False

    def test_relation_wildcard_matches_nested(self):
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("customer.name", "customer.*") is True
        assert field_matches_pattern("customer.email", "customer.*") is True

    def test_relation_wildcard_does_not_match_other_relation(self):
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("address.city", "customer.*") is False

    def test_exact_match(self):
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("customer.name", "customer.name") is True
        assert field_matches_pattern("customer.email", "customer.name") is False

    def test_deep_nested(self):
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("customer.address.city", "customer.address.*") is True


class TestFieldsAllowed:
    """Tests for fields_allowed function."""

    def test_all_fields_allowed(self):
        from django_flex.permissions import fields_allowed

        allowed, denied = fields_allowed(["id", "name"], ["*"])
        assert allowed is True
        assert denied is None

    def test_nested_field_denied_by_base_wildcard(self):
        from django_flex.permissions import fields_allowed

        allowed, denied = fields_allowed(["customer.email"], ["*"])
        assert allowed is False
        assert denied == "customer.email"

    def test_nested_field_allowed_by_relation_wildcard(self):
        from django_flex.permissions import fields_allowed

        allowed, denied = fields_allowed(["customer.email"], ["*", "customer.*"])
        assert allowed is True

    def test_mixed_fields(self):
        from django_flex.permissions import fields_allowed

        patterns = ["id", "name", "customer.name", "customer.phone"]
        allowed, denied = fields_allowed(["id", "customer.name"], patterns)
        assert allowed is True

        allowed, denied = fields_allowed(["id", "customer.email"], patterns)
        assert allowed is False
        assert denied == "customer.email"
