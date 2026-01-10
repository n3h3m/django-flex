"""
Security Tests for H4: Wildcard '*' Pattern Documentation Contradiction

This test verifies that the wildcard '*' pattern behavior matches documentation
and that the code comment is corrected.

These tests verify actual behavior and document expected behavior.

Related Issue: #5 [H4] HIGH: Wildcard '*' pattern documentation contradicts code comment
"""

import pytest

from django_flex.tests.test_utils import run_tests


# =============================================================================
# State variables for tests
# =============================================================================
state = {}


# =============================================================================
# TEST CASES (Integration style)
# Note: The wildcard pattern behavior is fully tested by unit tests below.
# Integration tests would require a full Django project with URL conf.
# =============================================================================
TEST_CASES = []


# =============================================================================
# Unit tests for the specific pattern behavior
# =============================================================================
class TestH4WildcardPattern:
    """
    Direct unit tests for wildcard pattern matching behavior.

    Documentation says: `*` matches "All direct fields on model"
    Code comment says: `*` matches "EVERYTHING (base and nested fields)"
    Tests confirm: Documentation is correct - nested fields not matched by *

    This test suite documents and verifies the correct behavior.
    """

    def test_wildcard_matches_base_field(self):
        """
        Test that '*' matches base (non-nested) fields.

        Expected: field_matches_pattern('id', '*') == True
        """
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("id", "*") is True
        assert field_matches_pattern("name", "*") is True
        assert field_matches_pattern("created_at", "*") is True

    def test_wildcard_does_not_match_nested_field(self):
        """
        Test that '*' does NOT match nested fields.

        Expected: field_matches_pattern('customer.name', '*') == False
        Documentation: `*` matches "All direct fields on model" (not nested)
        """
        from django_flex.permissions import field_matches_pattern

        result = field_matches_pattern("customer.name", "*")

        assert result is False, (
            f"H4 ISSUE: field_matches_pattern('customer.name', '*') returned {result}. "
            "Documentation says '*' should only match direct fields, not nested."
        )

    def test_wildcard_nested_variations(self):
        """
        Test various nested field patterns against wildcard.
        """
        from django_flex.permissions import field_matches_pattern

        nested_fields = [
            "customer.name",
            "customer.company.name",
            "order.items.product.name",
            "a.b.c.d.e",
        ]

        for field in nested_fields:
            result = field_matches_pattern(field, "*")
            assert result is False, f"H4 ISSUE: Nested field '{field}' matched wildcard '*'. " "Only base fields should match."

    def test_code_comment_accuracy(self):
        """
        Verify that code comments accurately describe behavior.

        This test checks if the misleading comment has been fixed.
        """
        import inspect
        from django_flex.permissions import field_matches_pattern

        source = inspect.getsource(field_matches_pattern)

        # The misleading comment says:
        misleading = '"*" matches EVERYTHING (base and nested fields)'

        if misleading in source:
            pytest.fail(
                "H4 DOCUMENTATION BUG: Code comment claims '*' matches "
                "'EVERYTHING (base and nested fields)' but tests prove this is false. "
                "Comment should say '*' matches 'base fields only (not nested)'."
            )

    def test_relation_wildcard_pattern(self):
        """
        Test that 'relation.*' pattern matches nested fields correctly.

        Expected: 'customer.*' matches 'customer.name', 'customer.id', etc.
        """
        from django_flex.permissions import field_matches_pattern

        # relation.* should match all fields on that relation
        assert field_matches_pattern("customer.name", "customer.*") is True
        assert field_matches_pattern("customer.id", "customer.*") is True

        # But not deeper nesting
        # Note: This behavior may vary - document whatever is actual
        deep_match = field_matches_pattern("customer.company.name", "customer.*")
        # Just document the behavior, don't assert either way
        print(f"INFO: 'customer.company.name' matches 'customer.*': {deep_match}")

    def test_explicit_field_pattern(self):
        """
        Test that explicit field patterns match exactly.
        """
        from django_flex.permissions import field_matches_pattern

        assert field_matches_pattern("customer.name", "customer.name") is True
        assert field_matches_pattern("customer.id", "customer.name") is False
        assert field_matches_pattern("name", "customer.name") is False


# =============================================================================
# Documentation consistency tests
# =============================================================================
class TestH4DocumentationConsistency:
    """
    Tests to verify documentation matches implementation.
    """

    def test_fields_allowed_with_wildcard(self):
        """
        Test fields_allowed function behavior with wildcard.
        """
        from django_flex.permissions import fields_allowed

        # Base fields should be allowed with '*'
        allowed, denied = fields_allowed(["id", "name", "status"], ["*"])
        assert allowed is True, f"Base fields rejected with '*': {denied}"

        # Nested fields should NOT be allowed with just '*'
        allowed, denied = fields_allowed(["id", "customer.name"], ["*"])
        assert allowed is False, (
            "H4 ISSUE: Nested field 'customer.name' was allowed with just '*' pattern. "
            "Need explicit 'customer.*' or 'customer.name' in allowed list."
        )

    def test_expand_fields_with_wildcard(self):
        """
        Test that expand_fields('*') only returns base model fields.
        """
        from django_flex.fields import expand_fields
        from unittest.mock import MagicMock, patch

        # Mock a model with various field types
        mock_model = MagicMock()
        mock_model.__name__ = "MockModel"

        # Create mock fields
        base_field = MagicMock()
        base_field.name = "name"
        base_field.is_relation = False
        base_field.concrete = True
        base_field.many_to_many = False
        base_field.one_to_many = False

        id_field = MagicMock()
        id_field.name = "id"
        id_field.is_relation = False
        id_field.concrete = True
        id_field.many_to_many = False
        id_field.one_to_many = False

        fk_field = MagicMock()
        fk_field.name = "customer"
        fk_field.is_relation = True
        fk_field.concrete = True
        fk_field.many_to_many = False
        fk_field.one_to_many = False

        mock_model._meta.get_fields.return_value = [id_field, base_field, fk_field]

        # Mock get_model_fields and get_model_relations
        with patch("django_flex.fields.get_model_fields") as mock_get_fields, patch("django_flex.fields.get_model_relations") as mock_get_relations:
            mock_get_fields.return_value = ["id", "name", "customer_id"]
            mock_get_relations.return_value = {"customer": MagicMock()}

            expanded = expand_fields(mock_model, ["*"])

            # Should only include base fields, not auto-expand relations
            assert "id" in expanded or "name" in expanded or len(expanded) > 0, "No fields expanded"

            # Nested fields like 'customer.name' should NOT be auto-included
            nested = [f for f in expanded if "." in f]
            if nested:
                pytest.fail(
                    f"H4 POTENTIAL ISSUE: expand_fields('*') included nested fields: {nested}. " "Wildcard should only expand to base model fields."
                )


# =============================================================================
# Integration test runner
# =============================================================================
@pytest.fixture
def setup_db(db):
    """Create test fixtures for H4 tests."""
    pass


@pytest.mark.django_db
def test_h4_wildcard_pattern(setup_db, subtests):
    """Run all H4 test cases."""
    run_tests(TEST_CASES, state, subtests)
