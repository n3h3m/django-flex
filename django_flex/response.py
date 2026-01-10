"""
Django-Flex Response Utilities

Handles response building and serialization for flexible queries.

Features:
- Nested response construction from field paths
- Automatic serialization of common types
- Response code management
"""

from django_flex.conf import flex_settings


def get_field_value(obj, field_path, json_fields=None, fk_fields=None):
    """
    Get value from object following dot notation path.

    Safely traverses nested objects and returns None if any
    part of the path is missing. For JSONFields, continues
    traversal into the JSON dict structure.

    For simple FK fields (e.g., "company" not "company.name"),
    returns the raw FK ID from the _id column without fetching
    the related object.

    Args:
        obj: Model instance
        field_path: Dot-notation path (e.g., "customer.name")
        json_fields: Optional set of JSONField names for the model
        fk_fields: Optional set of ForeignKey field names for the model

    Returns:
        Value at the path, or None if not found

    Examples:
        >>> get_field_value(booking, "status")
        "confirmed"
        >>> get_field_value(booking, "customer.name")
        "Aisha Khan"
        >>> get_field_value(service, "company", fk_fields={"company"})
        1  # Returns raw FK ID, no object fetch
        >>> get_field_value(customer, "metadata.settings.theme", {"metadata"})
        "dark"
    """
    if json_fields is None:
        json_fields = set()
    if fk_fields is None:
        fk_fields = set()

    parts = field_path.split(".")

    # Simple FK field (not nested) - use _id column directly for efficiency
    if len(parts) == 1 and parts[0] in fk_fields:
        return getattr(obj, f"{parts[0]}_id", None)

    value = obj

    for i, part in enumerate(parts):
        if value is None:
            return None

        # Check if this part is a JSONField
        if part in json_fields:
            # Get the JSONField value
            json_value = getattr(value, part, None)
            if json_value is None:
                return None
            # Continue traversing remaining parts as dict keys
            remaining_parts = parts[i + 1 :]
            for json_key in remaining_parts:
                if not isinstance(json_value, dict):
                    return None
                json_value = json_value.get(json_key)
                if json_value is None:
                    return None
            return json_value

        value = getattr(value, part, None)

    return value


def serialize_value(value):
    """
    Serialize a value for JSON response.

    Handles common Django types:
    - DateField, DateTimeField -> ISO format string
    - ForeignKey -> primary key string
    - UUID -> string

    Args:
        value: Value to serialize

    Returns:
        JSON-serializable value
    """
    if value is None:
        return None

    # DateTime/Date
    if hasattr(value, "isoformat"):
        return value.isoformat()

    # UUID
    if hasattr(value, "hex"):
        return str(value)

    # Related object not in fields list - just use pk
    if hasattr(value, "pk"):
        return str(value.pk)

    return value


def build_nested_response(obj, field_paths, json_fields=None, fk_fields=None):
    """
    Build nested dict response from object and field paths.

    Constructs a nested dictionary structure from a flat list of
    dot-notation field paths.

    Args:
        obj: Model instance
        field_paths: List of field paths (e.g., ["id", "customer.name"])
        json_fields: Optional set of JSONField names for proper JSON traversal
        fk_fields: Optional set of ForeignKey field names for efficient ID access

    Returns:
        Nested dictionary with field values

    Example:
        >>> build_nested_response(booking, ["id", "status", "customer.name", "customer.email"])
        {
            "id": "1",
            "status": "confirmed",
            "customer": {
                "name": "Aisha Khan",
                "email": "aisha@example.com"
            }
        }
    """
    if obj is None:
        return None

    result = {}

    for field_path in field_paths:
        parts = field_path.split(".")
        value = get_field_value(obj, field_path, json_fields, fk_fields)
        value = serialize_value(value)

        # Build nested structure
        current = result
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            # Handle case where current[part] is already a non-dict value (from JSONField)
            elif not isinstance(current[part], dict):
                break
            current = current[part]

        current[parts[-1]] = value

    return result


class FlexResponse:
    """
    Response builder for django-flex queries.

    Builds response data - success/error indicated by HTTP status codes.
    When ALWAYS_HTTP_200=True, all responses return HTTP 200 with status_code in payload.

    Example:
        >>> response = FlexResponse.ok(id=1, name="Test")
        >>> response.to_dict()
        {"id": 1, "name": "Test"}

        >>> response = FlexResponse.error("NOT_FOUND", "Object not found")
        >>> response.to_dict()
        {"error": "Object not found"}
    """

    # Map response codes to HTTP status codes
    STATUS_MAP = {
        "OK": 200,
        "OK_QUERY": 200,
        "CREATED": 201,
        "LIMIT_CLAMPED": 200,
        "BAD_REQUEST": 400,
        "INVALID_JSON": 400,
        "UNAUTHORIZED": 401,
        "PERMISSION_DENIED": 403,
        "NOT_FOUND": 404,
        "RATE_LIMITED": 429,
        "INTERNAL_ERROR": 500,
        "CREATE_FAILED": 400,
    }

    def __init__(self, code="OK", warning=False, error_message=None, **data):
        """
        Initialize a FlexResponse.

        Args:
            code: Response code key (e.g., "OK", "NOT_FOUND")
            warning: Whether this is a warning response
            error_message: Optional error message for error responses
            **data: Additional data to include in response
        """
        self.code = code
        self.warning = warning
        self.error_message = error_message
        self.data = data

    @property
    def success(self):
        """Whether the response indicates success."""
        return self.code in ("OK", "OK_QUERY", "CREATED", "LIMIT_CLAMPED")

    @property
    def http_status(self):
        """Get HTTP status code for this response."""
        return self.STATUS_MAP.get(self.code, 500)

    @classmethod
    def ok(cls, **data):
        """Create a successful response."""
        return cls(code="OK", **data)

    @classmethod
    def ok_query(cls, results, pagination=None, **data):
        """Create a successful query response."""
        response_data = {"results": results}
        if pagination:
            response_data["pagination"] = pagination
        response_data.update(data)
        return cls(code="OK_QUERY", **response_data)

    @classmethod
    def error(cls, code, message=None):
        """Create an error response."""
        return cls(code=code, error_message=message)

    @classmethod
    def warning_response(cls, code, **data):
        """Create a warning response (success with warning flag)."""
        return cls(code=code, warning=True, **data)

    # Messages for response codes
    MSG_MAP = {
        "OK": "Success",
        "OK_QUERY": "Query successful",
        "CREATED": "Created successfully",
        "LIMIT_CLAMPED": "Limit was clamped to maximum allowed",
        "BAD_REQUEST": "Bad request",
        "INVALID_JSON": "Invalid JSON in request body",
        "UNAUTHORIZED": "Authentication required",
        "PERMISSION_DENIED": "Permission denied",
        "NOT_FOUND": "Not found",
        "RATE_LIMITED": "Rate limit exceeded",
        "INTERNAL_ERROR": "Internal server error",
        "INVALID_FIELD": "Invalid field",
        "SAVE_FAILED": "Failed to save",
        "CREATE_FAILED": "Failed to create",
    }

    def to_dict(self, include_status_code=False):
        """
        Convert response to dictionary for JSON serialization.

        Args:
            include_status_code: If True, include standardized response fields

        When include_status_code is True (ALWAYS_HTTP_200 mode):
            - status_code: HTTP status code (200, 201, 400, etc.)
            - success: True/False
            - msg: Success message (for success responses)
            - error: Error message (for error responses)
            - warning: Warning message (for warning responses)
            Plus any additional data fields.
        """
        result = {}

        if include_status_code:
            result["status_code"] = self.http_status
            result["success"] = self.success

            if self.error_message:
                result["error"] = self.error_message
            elif not self.success and not self.error_message:
                result["error"] = self.MSG_MAP.get(self.code, "An error occurred")

            if self.warning:
                result["warning"] = self.MSG_MAP.get(self.code, "Warning")

        else:
            # Legacy mode (ALWAYS_HTTP_200=False)
            if self.warning:
                result["warning"] = True
                result["warning_code"] = self.code

            if self.error_message:
                result["error"] = self.error_message

        result.update(self.data)

        return result

    def to_json_response(self):
        """
        Convert to Django JsonResponse.

        When ALWAYS_HTTP_200 is True:
        - All responses return HTTP 200
        - Includes: status_code, success, msg/error/warning, plus data
        - If DEBUG=True and exception occurred, includes exception field

        When ALWAYS_HTTP_200 is False (default):
        - Uses traditional HTTP status codes
        - No status_code in payload
        """
        from django.http import JsonResponse
        from django.conf import settings
        from django_flex.conf import flex_settings

        if flex_settings.ALWAYS_HTTP_200:
            response_dict = self.to_dict(include_status_code=True)

            # Add exception details in DEBUG mode for internal errors
            if settings.DEBUG and self.code == "INTERNAL_ERROR" and self.error_message:
                response_dict["exception"] = self.error_message

            return JsonResponse(response_dict, status=200)
        else:
            # Traditional: use HTTP status codes
            return JsonResponse(self.to_dict(), status=self.http_status)
