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

    def test_wildcard_does_not_match_nested_fields(self):
        """\"*\" only matches base fields, NOT nested fields."""
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("customer.name", "*") is False
        assert field_matches_pattern("customer.address.city", "*") is False

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

    def test_nested_field_rejected_by_base_wildcard(self):
        """'*' does NOT allow nested fields - use 'relation.*' patterns."""
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

    def test_empty_patterns_denies_all(self):
        """Empty patterns list should deny all fields (deny-by-default)."""
        from django_flex.permissions import fields_allowed

        allowed, denied = fields_allowed(["id"], [])
        assert allowed is False
        assert denied == "id"

    def test_empty_patterns_allows_empty_request(self):
        """Empty patterns with empty request should pass."""
        from django_flex.permissions import fields_allowed

        allowed, denied = fields_allowed([], [])
        assert allowed is True


class TestNormalizeRoleConfig:
    """Tests for normalize_role_config function."""

    def test_star_shorthand_expands_to_full_access(self):
        from django_flex.permissions import normalize_role_config

        perm = normalize_role_config("*")
        assert perm["fields"] == ["*"]  # "*" matches base fields only (not nested)
        assert perm["filters"] == "*"
        assert perm["order_by"] == "*"
        assert perm["rows"] == "*"  # "*" means all rows
        assert "get" in perm["ops"]
        assert "list" in perm["ops"]
        assert "add" in perm["ops"]

    def test_empty_dict_grants_nothing(self):
        from django_flex.permissions import normalize_role_config

        perm = normalize_role_config({})
        assert perm["fields"] == []
        assert perm["filters"] == []
        assert perm["order_by"] == []
        assert perm["ops"] == []

    def test_dict_with_partial_config(self):
        from django_flex.permissions import normalize_role_config

        perm = normalize_role_config({"fields": ["id", "name"], "ops": ["get"]})
        assert perm["fields"] == ["id", "name"]
        assert perm["filters"] == []  # Default to empty
        assert perm["order_by"] == []  # Default to empty
        assert perm["ops"] == ["get"]
