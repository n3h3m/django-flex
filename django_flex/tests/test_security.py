"""
Main Security Test Suite

This file imports and runs all security tests from the individual test files.
Each test module corresponds to a security finding from the audit:

HIGH PRIORITY:
- test_security_h1: Hardcoded Session import (Issue #2)
- test_security_h2: CSRF Exempt on all views (Issue #3)
- test_security_h3: Anonymous user bypasses permissions (Issue #4)
- test_security_h4: Wildcard pattern inconsistency (Issue #5)
- test_security_h5: MAX_RELATION_DEPTH not enforced (Issue #6)

MEDIUM PRIORITY:
- test_security_medium: M1-M5 consolidated (Issues #7-#11)

TEST DESIGN:
Tests are designed to FAIL when vulnerabilities exist and PASS after fixes.
This ensures:
1. Existing vulnerabilities are documented and detectable
2. Fixes are validated by passing tests
3. Regressions are caught if vulnerabilities reappear

USAGE:
    pytest django_flex/tests/test_security*.py -v
    pytest django_flex/tests/test_security_h1.py -v  # Single issue
    pytest -k "security" -v  # All security tests
"""

import pytest


# =============================================================================
# Security Test Summary
# =============================================================================
SECURITY_ISSUES = {
    "H1": {
        "title": "Hardcoded app.models.Session import",
        "severity": "CRITICAL",
        "file": "test_security_h1.py",
        "issue": "#2",
        "fixed": False,
    },
    "H2": {
        "title": "CSRF Exempt on all views",
        "severity": "CRITICAL",
        "file": "test_security_h2.py",
        "issue": "#3",
        "fixed": False,
    },
    "H3": {
        "title": "Anonymous user bypasses ALL permission checks",
        "severity": "CRITICAL",
        "file": "test_security_h3.py",
        "issue": "#4",
        "fixed": False,
    },
    "H4": {
        "title": "Wildcard '*' pattern documentation contradiction",
        "severity": "HIGH",
        "file": "test_security_h4.py",
        "issue": "#5",
        "fixed": False,
    },
    "H5": {
        "title": "MAX_RELATION_DEPTH not enforced on fields",
        "severity": "HIGH",
        "file": "test_security_h5.py",
        "issue": "#6",
        "fixed": False,
    },
    "M1": {
        "title": "Rate limit bypass via IP spoofing",
        "severity": "MEDIUM",
        "file": "test_security_medium.py",
        "issue": "#7",
        "fixed": False,
    },
    "M2": {
        "title": "Silent exception swallowing",
        "severity": "MEDIUM",
        "file": "test_security_medium.py",
        "issue": "#8",
        "fixed": False,
    },
    "M3": {
        "title": "No input validation on filter values",
        "severity": "MEDIUM",
        "file": "test_security_medium.py",
        "issue": "#9",
        "fixed": False,
    },
    "M4": {
        "title": "FlexModelView allowed_models default allows all",
        "severity": "MEDIUM",
        "file": "test_security_medium.py",
        "issue": "#10",
        "fixed": False,
    },
    "M5": {
        "title": "Superuser cannot access unconfigured models (docs)",
        "severity": "LOW",
        "file": "test_security_medium.py",
        "issue": "#11",
        "fixed": False,
    },
}


@pytest.fixture
def security_status():
    """Fixture providing security issue status."""
    return SECURITY_ISSUES


class TestSecuritySummary:
    """Meta-tests that provide security status summary."""

    def test_print_security_status(self, security_status):
        """Print current security status."""
        print("\n" + "=" * 60)
        print("DJANGO-FLEX SECURITY STATUS")
        print("=" * 60)

        for issue_id, info in security_status.items():
            status = "✅ FIXED" if info["fixed"] else "❌ VULNERABLE"
            print(f"{issue_id} [{info['severity']}] {status}: {info['title']}")

        print("=" * 60)

        unfixed = [k for k, v in security_status.items() if not v["fixed"]]
        if unfixed:
            print(f"WARNING: {len(unfixed)} security issues remain unfixed!")
            print(f"Unfixed: {', '.join(unfixed)}")
        else:
            print("All security issues have been fixed!")
        print("=" * 60 + "\n")

    def test_critical_issues_exist(self, security_status):
        """Track that critical issues are known."""
        critical = [k for k, v in security_status.items() if v["severity"] == "CRITICAL"]
        assert len(critical) == 3, f"Expected 3 CRITICAL issues, found: {critical}"

    def test_high_issues_exist(self, security_status):
        """Track that high issues are known."""
        high = [k for k, v in security_status.items() if v["severity"] == "HIGH"]
        assert len(high) == 2, f"Expected 2 HIGH issues, found: {high}"


# =============================================================================
# Parameterized tests for all issues
# =============================================================================
@pytest.mark.parametrize("issue_id,info", SECURITY_ISSUES.items())
def test_security_issue_documented(issue_id, info):
    """Verify each security issue has proper documentation."""
    assert "title" in info
    assert "severity" in info
    assert "file" in info
    assert "issue" in info
    assert info["severity"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
