"""
Tests for django_flex.fields module.
"""

import pytest


class TestParseFields:
    """Tests for parse_fields function."""

    def test_simple_fields(self):
        from django_flex.fields import parse_fields

        result = parse_fields("name, email")
        assert result == ["name", "email"]

    def test_dotted_fields(self):
        from django_flex.fields import parse_fields

        result = parse_fields("id, customer.name, customer.email")
        assert result == ["id", "customer.name", "customer.email"]

    def test_wildcard(self):
        from django_flex.fields import parse_fields

        result = parse_fields("*")
        assert result == ["*"]

    def test_relation_wildcard(self):
        from django_flex.fields import parse_fields

        result = parse_fields("id, customer.*")
        assert result == ["id", "customer.*"]

    def test_empty_returns_wildcard(self):
        from django_flex.fields import parse_fields

        result = parse_fields("")
        assert result == ["*"]

    def test_none_returns_wildcard(self):
        from django_flex.fields import parse_fields

        result = parse_fields(None)
        assert result == ["*"]

    def test_strips_whitespace(self):
        from django_flex.fields import parse_fields

        result = parse_fields("  name  ,  email  ")
        assert result == ["name", "email"]


class TestExtractRelations:
    """Tests for extract_relations function."""

    def test_no_relations(self):
        from django_flex.fields import extract_relations

        relations = extract_relations(["id", "status", "name"])
        assert relations == set()

    def test_single_relation(self):
        from django_flex.fields import extract_relations

        relations = extract_relations(["id", "customer.name", "customer.email"])
        assert relations == {"customer"}

    def test_nested_relation(self):
        from django_flex.fields import extract_relations

        relations = extract_relations(["id", "customer.address.city"])
        assert relations == {"customer__address"}

    def test_multiple_relations(self):
        from django_flex.fields import extract_relations

        relations = extract_relations(["id", "customer.name", "address.city", "cleaner.phone"])
        assert relations == {"customer", "address", "cleaner"}
