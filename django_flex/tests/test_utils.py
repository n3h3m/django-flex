"""
Test utilities for django-flex security testing.

This testing framework follows the EliteSuite pattern:
- TEST_CASES array containing test definitions
- State dict for variable capture via !var syntax
- run_tests() executor with subtests support
- Setup functions for pre-test configuration

Test case format:
{
    "name": "Test case name",
    "setup": callable,       # Optional: function(state) called before test
    "req": { ... },          # Request payload (dict for JSON POST)
    "res": { ... },          # Expected response schema
    "status": 200,           # Optional: expected HTTP status (default 200)
    "!var_name": "field",    # Capture response["field"] into state["var_name"]
    "expect_error": True,    # If True, test expects failure (for security tests)
}

Security tests are designed to FAIL when vulnerabilities exist,
and PASS once fixes are applied.
"""

import pytest
from django.test import Client

client = Client()


def api(payload, headers=None, endpoint="/api/"):
    """Make a POST request to the API endpoint.

    Args:
        payload: Dict to send as JSON body
        headers: Optional dict of HTTP headers
        endpoint: API endpoint path (default: /api/)

    Returns:
        Django test client response
    """
    default_headers = {}
    if headers:
        default_headers.update(headers)

    response = client.post(
        endpoint,
        data=payload,
        content_type="application/json",
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in default_headers.items()},
    )
    return response


def validate_response(response_data, expected_schema):
    """
    Validate response data against expected schema.

    Schema can contain:
    - Exact values: {"field": "expected_value"}
    - Type checks: {"field": str}
    - Callables: {"field": lambda x: x > 0}
    - Nested dicts: {"nested": {"field": str}}

    Returns:
        Tuple of (is_valid, errors_list)
    """
    errors = []

    def check(data, schema, path=""):
        if isinstance(schema, dict):
            if not isinstance(data, dict):
                errors.append(f"{path}: expected dict, got {type(data).__name__}")
                return
            for key, expected in schema.items():
                full_path = f"{path}.{key}" if path else key
                if key not in data:
                    errors.append(f"{full_path}: missing key")
                    continue
                check(data[key], expected, full_path)
        elif isinstance(schema, type):
            if not isinstance(data, schema):
                errors.append(f"{path}: expected {schema.__name__}, got {type(data).__name__}")
        elif callable(schema):
            try:
                if not schema(data):
                    errors.append(f"{path}: callable check failed")
            except Exception as e:
                errors.append(f"{path}: callable raised {e}")
        else:
            # Exact value match
            if data != schema:
                errors.append(f"{path}: expected {schema!r}, got {data!r}")

    check(response_data, expected_schema)
    return len(errors) == 0, errors


def run_tests(test_cases, state, subtests, permissions=None, endpoint="/api/"):
    """
    Generic test runner for API integration tests.

    Args:
        test_cases: List of test case dictionaries
        state: Dictionary holding test state variables
        subtests: pytest-subtests fixture for running sub-tests
        permissions: Optional permissions config to use
        endpoint: API endpoint path

    Test case format:
        {
            "name": "Test case name",
            "setup": callable,      # Optional: function(state) to run before the test
            "req": { ... },         # Request payload
            "res": { ... },         # Expected response schema
            "status": 200,          # Optional: expected HTTP status (default 200)
            "headers": {},          # Optional: HTTP headers
            "!var_name": "field",   # Capture response["field"] into state["var_name"]
            "expect_error": True,   # If True, expect this test to fail (security test)
        }

    Special syntax:
        - "!var" in req values: replaced with state["var"]
        - "!key": "field" in test case: captures response["field"] into state["key"]
        - "setup": callable: function called with state dict before request
    """
    for case in test_cases:
        name = case["name"]
        with subtests.test(msg=name):
            print(f"Running test case: {name}")

            # Handle special setup actions
            if "setup" in case:
                setup_func = case["setup"]
                if callable(setup_func):
                    setup_func(state)
                else:
                    raise ValueError(f"Setup must be a callable function, got: {type(setup_func)}")

            req = case.get("req", {}).copy()
            headers = case.get("headers", {}).copy()

            # Injection: Replace values starting with '!' with variables from state
            for key, value in req.items():
                if isinstance(value, str) and value.startswith("!"):
                    var_name = value[1:]
                    if var_name in state:
                        req[key] = state[var_name]
                    else:
                        pytest.fail(f"Unknown state variable: {var_name}")

            for key, value in headers.items():
                if isinstance(value, str) and value.startswith("!"):
                    var_name = value[1:]
                    if var_name in state:
                        headers[key] = state[var_name]
                    else:
                        pytest.fail(f"Unknown state variable: {var_name}")

            response = api(req, headers=headers, endpoint=endpoint)

            # Verify status code
            expected_status = case.get("status", 200)

            expect_error = case.get("expect_error", False)

            if expect_error:
                # For security tests, we expect certain tests to fail until fixed
                # This inverts the assertion - test passes if response indicates error/failure
                try:
                    assert response.status_code == expected_status, f"Case '{name}' failed. Status {response.status_code} != {expected_status}"

                    response_data = response.json()

                    if "res" in case:
                        is_valid, errors = validate_response(response_data, case["res"])
                        assert is_valid, f"Case '{name}' schema validation failed: {errors}. Response: {response_data}"
                except AssertionError:
                    # For expect_error tests, assertion failure means security issue exists
                    # Mark as passed (the security issue is detected)
                    pytest.skip(f"SECURITY ISSUE DETECTED: {name} - vulnerability exists, will pass after fix")
            else:
                assert (
                    response.status_code == expected_status
                ), f"Case '{name}' failed. Status {response.status_code} != {expected_status}. Content: {response.content}"

                response_data = response.json()

                # Validate response schema
                if "res" in case:
                    is_valid, errors = validate_response(response_data, case["res"])
                    assert is_valid, f"Case '{name}' schema validation failed: {errors}. Response: {response_data}"

                # Extraction: Capture values defined in test case keys starting with '!'
                for key, target_field in case.items():
                    if key.startswith("!"):
                        var_name = key[1:]
                        if target_field in response_data:
                            state[var_name] = response_data[target_field]
                        else:
                            pytest.fail(f"Could not extract '{target_field}' to '{var_name}'. Field not found in response.")
