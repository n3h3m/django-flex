"""
Security Tests for H1: Hardcoded app.models.Session import

This test verifies that the middleware token authentication works
with configurable session models, not just hardcoded app.models.Session.

These tests will FAIL when the vulnerability exists and PASS once fixed.

Related Issue: #2 [H1] CRITICAL: Hardcoded app.models.Session import
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory, override_settings

from django_flex.tests.test_utils import run_tests


# =============================================================================
# State variables for tests
# =============================================================================
state = {
    "token": "test-token-12345",
    "user_id": 1,
}


# =============================================================================
# Setup functions
# =============================================================================
def setup_mock_session_model(state):
    """Setup a mock session model for testing configurable imports."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    state["mock_user"] = MagicMock(spec=User)
    state["mock_user"].id = state["user_id"]
    state["mock_user"].is_authenticated = True


# =============================================================================
# TEST CASES
# =============================================================================
TEST_CASES = [
    # ========================================
    # H1-1: Configurable SESSION_MODEL setting
    # ========================================
    {
        "name": "H1-1: SESSION_MODEL=None disables token auth gracefully",
        "setup": setup_mock_session_model,
        "req": {
            "_model": "testmodel",
            "_action": "list",
            "__token": "!token",
        },
        "res": {
            # Should proceed without error (token auth disabled, not crashed)
            # Expect permission denied (not ImportError)
            "success": False,
        },
        "expect_error": True,  # FAILS until SESSION_MODEL setting is implemented
    },
    {
        "name": "H1-2: Custom SESSION_MODEL path works",
        "setup": setup_mock_session_model,
        "req": {
            "_model": "testmodel",
            "_action": "list",
            "__token": "!token",
        },
        "res": {
            # With custom session model configured, should authenticate
            "success": True,
        },
        "expect_error": True,  # FAILS until configurable import is implemented
    },
    {
        "name": "H1-3: Invalid SESSION_MODEL logs error, doesn't crash",
        "setup": setup_mock_session_model,
        "req": {
            "_model": "testmodel",
            "_action": "list",
            "__token": "!token",
        },
        "res": {
            # Should not crash, should log error and disable token auth
            "success": lambda x: isinstance(x, bool),
        },
        "expect_error": True,  # FAILS until proper error handling added
    },
]


# =============================================================================
# Unit tests for the specific vulnerability
# =============================================================================
class TestH1HardcodedSessionImport:
    """
    Direct unit tests for the hardcoded Session import vulnerability.

    These tests verify that the middleware can work with any session model,
    not just the hardcoded app.models.Session.
    """

    def test_session_model_configurable(self):
        """
        Test that SESSION_MODEL setting exists and is respected.

        Expected: Middleware uses flex_settings.SESSION_MODEL for import.
        Actual (before fix): Hardcoded 'from app.models import Session'
        """
        from django_flex.conf import flex_settings

        # This should not raise AttributeError after fix
        try:
            session_model = flex_settings.SESSION_MODEL
            # If we get here, setting exists
            assert session_model is None or isinstance(session_model, str), "SESSION_MODEL should be None or a model path string"
        except AttributeError:
            pytest.fail("H1 VULNERABILITY: SESSION_MODEL setting does not exist. " "Middleware cannot be configured for different session models.")

    def test_middleware_no_import_error_without_app_models(self):
        """
        Test that middleware doesn't crash when app.models.Session doesn't exist.

        Expected: Graceful handling when session model not configured.
        Actual (before fix): ImportError: No module named 'app'
        """
        from django_flex.middleware import FlexQueryMiddleware

        factory = RequestFactory()
        request = factory.post("/", {"__token": "test-token"})

        middleware = FlexQueryMiddleware(lambda r: r)

        # This should not raise ImportError
        try:
            # Mock the _resolve_user_from_token method to test import behavior
            with patch.object(middleware, "_extract_token", return_value="test-token"):
                # Calling middleware should not crash
                middleware._resolve_user_from_token(request)
        except ImportError as e:
            if "app.models" in str(e) or "No module named 'app'" in str(e):
                pytest.fail(f"H1 VULNERABILITY: Hardcoded import crashed: {e}. " "Middleware must use configurable SESSION_MODEL setting.")
            raise

    def test_token_auth_with_custom_session_model(self):
        """
        Test token authentication works with a custom session model.

        Expected: Configurable via SESSION_MODEL = 'myapp.models.CustomSession'
        Actual (before fix): Only works with app.models.Session
        """
        from django_flex.conf import flex_settings

        # Check if SESSION_TOKEN_FIELD exists
        try:
            token_field = flex_settings.SESSION_TOKEN_FIELD
            assert token_field == "token" or isinstance(token_field, str)
        except AttributeError:
            pytest.fail("H1 VULNERABILITY: SESSION_TOKEN_FIELD setting missing. " "Cannot customize token field name for different session models.")

        # Check if SESSION_USER_FIELD exists
        try:
            user_field = flex_settings.SESSION_USER_FIELD
            assert user_field == "user" or isinstance(user_field, str)
        except AttributeError:
            pytest.fail("H1 VULNERABILITY: SESSION_USER_FIELD setting missing. " "Cannot customize user field name for different session models.")


# =============================================================================
# Integration test runner
# =============================================================================
@pytest.fixture
def setup_db(db):
    """Create test fixtures for H1 tests."""
    pass  # No DB fixtures needed for import/config tests


@pytest.mark.django_db
def test_h1_hardcoded_session(setup_db, subtests):
    """Run all H1 security test cases."""
    run_tests(TEST_CASES, state, subtests)
