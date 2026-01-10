"""
Security Tests for H2: CSRF Exempt on All Views

This test verifies that CSRF protection is enabled by default,
not disabled via @csrf_exempt decorator on all views.

These tests will FAIL when the vulnerability exists and PASS once fixed.

Related Issue: #3 [H2] CRITICAL: CSRF Exempt on All Views
"""

import pytest
from django.test import Client, RequestFactory, override_settings
from django.middleware.csrf import get_token
from unittest.mock import patch, MagicMock

from django_flex.tests.test_utils import run_tests


# =============================================================================
# State variables for tests
# =============================================================================
state = {
    "csrf_token": None,
}


# =============================================================================
# Setup functions
# =============================================================================
def setup_csrf_token(state):
    """Get a CSRF token for testing."""
    client = Client()
    client.get("/")  # Prime the session
    state["csrf_token"] = client.cookies.get("csrftoken", MagicMock()).value


# =============================================================================
# TEST CASES
# =============================================================================
TEST_CASES = [
    # ========================================
    # H2-1: CSRF protection should be enabled by default
    # ========================================
    {
        "name": "H2-1: Request without CSRF token rejected by default",
        "req": {
            "_model": "testmodel",
            "_action": "add",
            "name": "test",
        },
        "status": 403,  # CSRF failure
        "res": {},
        "expect_error": True,  # FAILS until CSRF enabled by default
    },
    {
        "name": "H2-2: Request with valid CSRF token accepted",
        "setup": setup_csrf_token,
        "headers": {
            "X-CSRFToken": "!csrf_token",
        },
        "req": {
            "_model": "testmodel",
            "_action": "list",
        },
        "status": 200,
        "res": {
            "success": lambda x: isinstance(x, bool),
        },
        "expect_error": True,  # FAILS until CSRF handling implemented
    },
]


# =============================================================================
# Unit tests for the specific vulnerability
# =============================================================================
class TestH2CSRFExempt:
    """
    Direct unit tests for the CSRF exempt vulnerability.

    These tests verify that CSRF protection is enabled by default
    and can be optionally disabled via configuration.
    """

    def test_csrf_exempt_setting_exists(self):
        """
        Test that CSRF_EXEMPT setting exists in configuration.

        Expected: flex_settings.CSRF_EXEMPT exists with False default
        Actual (before fix): No setting, always exempt
        """
        from django_flex.conf import flex_settings

        try:
            csrf_exempt = flex_settings.CSRF_EXEMPT
            assert csrf_exempt is False, "H2 VULNERABILITY: CSRF_EXEMPT should default to False for security. " f"Actual default: {csrf_exempt}"
        except AttributeError:
            pytest.fail("H2 VULNERABILITY: CSRF_EXEMPT setting does not exist. " "All views are unconditionally CSRF exempt - XSS attack vector!")

    def test_flexqueryview_not_csrf_exempt_by_default(self):
        """
        Test that FlexQueryView doesn't have @csrf_exempt applied unconditionally.

        Expected: CSRF protection enabled unless CSRF_EXEMPT=True in settings
        Actual (before fix): @method_decorator(csrf_exempt) on all views
        """
        from django_flex.views import FlexQueryView
        import inspect

        # Get the class source or check dispatch method
        dispatch = getattr(FlexQueryView, "dispatch", None)

        if dispatch:
            # Check if csrf_exempt is in the decorators
            # This is a heuristic check - looking for csrf_exempt marker
            if hasattr(dispatch, "csrf_exempt") and dispatch.csrf_exempt:
                pytest.fail("H2 VULNERABILITY: FlexQueryView.dispatch has csrf_exempt=True. " "CSRF protection is unconditionally disabled!")

    def test_csrf_token_required_for_mutations(self):
        """
        Test that mutation operations require CSRF token.

        Expected: add/edit/delete require CSRF token
        Actual (before fix): All operations bypass CSRF check
        """
        client = Client(enforce_csrf_checks=True)

        # Try to perform a mutation without CSRF token
        response = client.post("/api/", {"_model": "testmodel", "_action": "add", "name": "test"}, content_type="application/json")

        # If CSRF is properly enforced, should get 403
        if response.status_code != 403:
            pytest.fail(
                f"H2 VULNERABILITY: Mutation accepted without CSRF token (status {response.status_code}). "
                "Cross-Site Request Forgery attack is possible!"
            )

    def test_csrf_exempt_setting_disables_protection(self):
        """
        Test that CSRF_EXEMPT=True explicitly disables protection.

        Expected: When CSRF_EXEMPT=True, requests work without CSRF token
        """
        # This is the opt-in behavior for token-based API authentication
        pass  # Placeholder - only relevant after fix is implemented


# =============================================================================
# Attack simulation tests
# =============================================================================
class TestH2AttackSimulation:
    """
    Simulated attack scenarios demonstrating CSRF vulnerability impact.
    """

    def test_cross_site_delete_attack(self):
        """
        Simulate a cross-site delete attack.

        Attack scenario:
        1. Victim is logged into app
        2. Attacker hosts malicious page with form
        3. Form auto-submits DELETE request to victim's session
        4. Victim's data is deleted without consent
        """
        client = Client(enforce_csrf_checks=True)

        # Simulate logged-in user session (victim)
        # In real attack, victim's browser would have session cookie

        # Attacker's malicious form data
        attack_payload = {
            "_model": "booking",
            "_action": "delete",
            "id": 1,
        }

        # Cross-origin POST (no CSRF token)
        response = client.post(
            "/api/",
            attack_payload,
            content_type="application/json",
            # No Referer, no CSRF token - simulating cross-origin
        )

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("success") is True:
                    pytest.fail(
                        "H2 CRITICAL VULNERABILITY: Cross-site DELETE attack succeeded! " "Attacker can delete victim's data without CSRF token."
                    )
            except Exception:
                pass  # Response wasn't JSON, might be 403 or error

    def test_cross_site_data_modification(self):
        """
        Simulate a cross-site data modification attack.
        """
        client = Client(enforce_csrf_checks=True)

        attack_payload = {
            "_model": "user",
            "_action": "edit",
            "_id": 1,
            "email": "attacker@evil.com",  # Change victim's email
        }

        response = client.post(
            "/api/",
            attack_payload,
            content_type="application/json",
        )

        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("success") is True:
                    pytest.fail(
                        "H2 CRITICAL VULNERABILITY: Cross-site EDIT attack succeeded! " "Attacker can modify victim's data without CSRF token."
                    )
            except Exception:
                pass


# =============================================================================
# Integration test runner
# =============================================================================
@pytest.fixture
def setup_db(db):
    """Create test fixtures for H2 tests."""
    pass


@pytest.mark.django_db
def test_h2_csrf_exempt(setup_db, subtests):
    """Run all H2 security test cases."""
    run_tests(TEST_CASES, state, subtests)
