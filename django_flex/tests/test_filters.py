"""
Tests for django_flex.filters module.
"""

import pytest
from django.db.models import Q


class TestParseFilterKey:
    """Tests for parse_filter_key function."""

    def test_simple_field(self):
        from django_flex.filters import parse_filter_key

        field, op = parse_filter_key("status")
        assert field == "status"
        assert op is None

    def test_dotted_field(self):
        from django_flex.filters import parse_filter_key

        field, op = parse_filter_key("customer.name")
        assert field == "customer__name"
        assert op is None

    def test_operator_suffix(self):
        from django_flex.filters import parse_filter_key

        field, op = parse_filter_key("customer.address.zip.lt")
        assert field == "customer__address__zip"
        assert op == "lt"

    def test_icontains_operator(self):
        from django_flex.filters import parse_filter_key

        field, op = parse_filter_key("customer.name.icontains")
        assert field == "customer__name"
        assert op == "icontains"

    def test_in_operator(self):
        from django_flex.filters import parse_filter_key

        field, op = parse_filter_key("status.in")
        assert field == "status"
        assert op == "in"

    def test_gte_operator(self):
        from django_flex.filters import parse_filter_key

        field, op = parse_filter_key("total_cents.gte")
        assert field == "total_cents"
        assert op == "gte"


class TestBuildQObject:
    """Tests for build_q_object function."""

    def test_empty_filters(self):
        from django_flex.filters import build_q_object

        q = build_q_object({})
        assert str(q) == str(Q())

    def test_simple_equality(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"status": "confirmed"})
        expected = Q(status="confirmed")
        assert str(q) == str(expected)

    def test_multiple_conditions_are_anded(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"status": "confirmed", "total_cents": 100})
        # Q objects may have different order, so check both conditions are present
        assert "status" in str(q)
        assert "total_cents" in str(q)

    def test_operator_lt(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"price.lt": 100})
        expected = Q(price__lt=100)
        assert str(q) == str(expected)

    def test_operator_gte(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"price.gte": 50})
        expected = Q(price__gte=50)
        assert str(q) == str(expected)

    def test_operator_icontains(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"name.icontains": "Khan"})
        expected = Q(name__icontains="Khan")
        assert str(q) == str(expected)

    def test_operator_in(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"status.in": ["confirmed", "completed"]})
        expected = Q(status__in=["confirmed", "completed"])
        assert str(q) == str(expected)

    def test_not_composition(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"not": {"status": "cancelled"}})
        expected = ~Q(status="cancelled")
        assert str(q) == str(expected)

    def test_nested_dotted_filter(self):
        from django_flex.filters import build_q_object

        q = build_q_object({"customer.address.zip.lt": 3000})
        expected = Q(customer__address__zip__lt=3000)
        assert str(q) == str(expected)


class TestExtractFilterKeys:
    """Tests for extract_filter_keys function."""

    def test_simple_filters(self):
        from django_flex.filters import extract_filter_keys

        filters = {"name": "Test", "status": "active"}
        keys = extract_filter_keys(filters)
        assert "name" in keys
        assert "status" in keys

    def test_operator_filters(self):
        from django_flex.filters import extract_filter_keys

        filters = {"price.gte": 100, "name.icontains": "clean"}
        keys = extract_filter_keys(filters)
        assert "price.gte" in keys
        assert "name.icontains" in keys

    def test_or_composition(self):
        from django_flex.filters import extract_filter_keys

        filters = {"or": {"name": "Test", "status": "active"}}
        keys = extract_filter_keys(filters)
        assert "name" in keys
        assert "status" in keys

    def test_not_composition(self):
        from django_flex.filters import extract_filter_keys

        filters = {"not": {"status": "cancelled"}}
        keys = extract_filter_keys(filters)
        assert "status" in keys

    def test_empty_filters(self):
        from django_flex.filters import extract_filter_keys

        keys = extract_filter_keys({})
        assert keys == []

    def test_nested_and(self):
        from django_flex.filters import extract_filter_keys

        filters = {"and": {"name": "Test", "price.lt": 200}}
        keys = extract_filter_keys(filters)
        assert "name" in keys
        assert "price.lt" in keys
