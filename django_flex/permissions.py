"""
Django-Flex Permission System

Provides row-level, field-level, and operation-level access control
following the Principle of Least Privilege (deny by default, explicitly grant).

Integrates with Django's built-in auth system:
- User.groups for role-based access
- User.is_superuser for admin bypass
- User.is_staff for staff-level access

Features:
- Row-level: Which rows can the user see (Q filters)
- Field-level: Which fields can the user access (including relations)
- Operation-level: Which actions can the user perform (get, list, add, edit, delete)
- Filter-level: Which fields can the user filter on
- Order-level: Which fields can the user order by

Usage:
    from django_flex import check_permission

    row_filter, allowed_fields = check_permission(
        user, "booking", "query", requested_fields
    )
    queryset = Booking.objects.filter(row_filter)
"""

from django.db.models import Q

from django_flex.conf import flex_settings
from django_flex.filters import OPERATORS


class FlexPermission:
    """
    Base permission class for django-flex.

    Subclass this to create custom permission logic, similar to
    Django REST Framework's permission classes.

    Example:
        class IsOwnerPermission(FlexPermission):
            def has_permission(self, request, model_name, action):
                return request.user.is_authenticated

            def get_row_filter(self, request, model_name):
                return Q(owner=request.user)

            def get_allowed_fields(self, request, model_name):
                return ['*', 'owner.name']
    """

    def has_permission(self, request, model_name, action):
        """Check if request has permission for action on model."""
        return True

    def get_row_filter(self, request, model_name):
        """Return Q object to filter rows user can access."""
        return Q()

    def get_allowed_fields(self, request, model_name):
        """Return list of allowed field patterns."""
        return ["*"]

    def get_allowed_filters(self, request, model_name):
        """Return list of allowed filter keys."""
        return []

    def get_allowed_ordering(self, request, model_name):
        """Return list of allowed order_by values."""
        return []


def field_matches_pattern(field: str, pattern: str) -> bool:
    """
    Check if a field matches an allowed pattern.

    Args:
        field: Field path to check (e.g., 'name', 'customer.email')
        pattern: Pattern to match against

    Pattern types:
        '*' - All base fields on model (NOT nested)
        'customer.*' - All fields on customer relation
        'customer.email' - Exact field match

    Returns:
        True if field matches pattern, False otherwise

    Examples:
        >>> field_matches_pattern('name', '*')
        True
        >>> field_matches_pattern('customer.name', '*')
        False
        >>> field_matches_pattern('customer.name', 'customer.*')
        True
    """
    # "*" matches only base (non-nested) fields
    if pattern == "*":
        # Nested fields contain ".", so only match if no dots
        return "." not in field

    if pattern.endswith(".*"):
        # Relation wildcard: customer.* matches customer.name, customer.email
        prefix = pattern[:-2]
        return field.startswith(prefix + ".")

    # Exact match
    return field == pattern


def fields_allowed(requested_fields, allowed_patterns):
    """
    Check if all requested fields are allowed by the patterns.

    Args:
        requested_fields: List of field names to check
        allowed_patterns: List of allowed patterns

    Returns:
        Tuple of (is_allowed, denied_field)
    """
    # Empty patterns = nothing allowed (deny by default)
    if not allowed_patterns:
        if requested_fields:
            return False, requested_fields[0]
        return True, None

    for field in requested_fields:
        allowed = False
        for pattern in allowed_patterns:
            if field_matches_pattern(field, pattern):
                allowed = True
                break
        if not allowed:
            return False, field
    return True, None


def normalize_role_config(perm):
    """
    Normalize a role permission config.

    Supports shorthand:
    - "*" -> full access (all rows, fields, filters, order_by, ops)
    - {}, [], "", None, or any falsy value -> no access (deny all)

    Args:
        perm: Role permission (string "*" or dict)

    Returns:
        Normalized dict with all keys present
    """
    # "*" shorthand = full access
    if perm == "*":
        return {
            "rows": "*",  # "*" means all rows (no filter)
            "fields": ["*"],  # "*" matches base fields only (not nested)
            "filters": "*",  # All filters allowed
            "order_by": "*",  # All order_by allowed
            "ops": ["get", "list", "add", "edit", "delete"],
        }

    # Empty or non-dict = no access (deny all)
    if not isinstance(perm, dict) or not perm:
        return {
            "rows": lambda user: Q(pk=-1),  # Match nothing
            "fields": [],
            "filters": [],
            "order_by": [],
            "ops": [],
        }

    # Return as-is but with defaults for missing keys (empty = deny)
    return {
        "rows": perm.get("rows") or None,
        "fields": perm.get("fields") or [],
        "filters": perm.get("filters") or [],
        "order_by": perm.get("order_by") or [],
        "ops": perm.get("ops") or perm.get("operations") or [],
    }


def get_user_role(user, model_name=None, permissions=None):
    """
    Get the user's role for permission checking.

    Role resolution order:
    1. Custom ROLE_RESOLVER callable (if configured)
    2. superuser -> 'superuser' (bypasses all checks)
    3. staff -> 'staff'
    4. First matching group name (lowercase)
    5. 'authenticated' if logged in
    6. 'anon' if anonymous (for rate limiting)

    Args:
        user: Django User instance
        model_name: Optional model name (passed to custom resolver)
        permissions: Optional permissions config (for custom role lookup)

    Returns:
        Either:
        - Tuple of (role_name, row_filter) if resolver provides row filter
        - Role name string if no row filter from resolver
    """
    if user is None:
        return "anon"

    if not user.is_authenticated:
        return "anon"

    # Check for custom role resolver first
    resolver = flex_settings.ROLE_RESOLVER
    if resolver and callable(resolver):
        result = resolver(user, model_name)
        if result:
            # Resolver can return either:
            # - string: just the role name
            # - tuple: (role_name, row_filter Q object)
            if isinstance(result, tuple) and len(result) == 2:
                role, row_filter = result
                return (role.lower(), row_filter)
            else:
                return result.lower()

    # Default role resolution
    if user.is_superuser:
        return "superuser"

    if user.is_staff:
        return "staff"

    # Use Django's built-in groups
    if hasattr(user, "groups"):
        # Get the first group name as the role
        group = user.groups.first()
        if group:
            return group.name.lower()

    # Fallback for authenticated users with no group
    return "authenticated"


def check_permission(user, model_name, action, requested_fields, permissions=None):
    """
    Check if user has permission to perform action on model with requested fields.

    This is the main permission check function. It validates:
    1. User has a valid role (including 'anon' for unauthenticated)
    2. Model is configured in permissions
    3. Role has access to the model
    4. Action is allowed for the role
    5. All requested fields are allowed

    H3 fix: Anonymous users are handled via 'anon' role in permissions config.
    If 'anon' role is configured for a model, anonymous access is allowed with
    that role's restrictions. If 'anon' is not configured, access is denied.

    Row filter resolution:
    1. If config specifies "rows", use that
    2. Else if ROLE_RESOLVER returned a row_filter, use that
    3. Else no filter (all rows)

    Args:
        user: Django User instance (or None for anonymous)
        model_name: Model name (lowercase)
        action: Action name (get, list, add, edit, delete)
        requested_fields: List of field paths to access
        permissions: Optional permissions dict (uses settings if not provided)

    Returns:
        Tuple of (row_filter, fields) - Q object for row filtering, validated fields list

    Raises:
        PermissionError: If permission denied
    """
    if permissions is None:
        permissions = flex_settings.PERMISSIONS

    model_name = model_name.lower()

    # Check if model is accessible (BEFORE role check - deny by default)
    if model_name not in permissions:
        raise PermissionError(f"Access denied: model '{model_name}' not configured")

    model_perms = permissions[model_name]

    # H3 fix: Handle anonymous users via 'anon' role
    is_anonymous = user is None or not getattr(user, "is_authenticated", False)

    if is_anonymous:
        # Anonymous user - must have 'anon' role configured
        role = "anon"
        resolver_row_filter = None
        if role not in model_perms:
            raise PermissionError(f"Anonymous access denied: no 'anon' role configured for '{model_name}'")
    else:
        # Get user's role (may return tuple with row_filter)
        role_result = get_user_role(user, model_name, permissions)
        resolver_row_filter = None

        if isinstance(role_result, tuple):
            role, resolver_row_filter = role_result
        else:
            role = role_result

    if not role:
        raise PermissionError("No role could be determined for user")

    # Check if role has access to this model
    if role not in model_perms:
        raise PermissionError(f"Access denied: role '{role}' cannot access '{model_name}'")

    # Normalize the role config (handles "*" shorthand and empty {})
    perm = normalize_role_config(model_perms[role])

    # Superuser with "*" config bypasses remaining checks
    if not is_anonymous and user.is_superuser and model_perms[role] == "*":
        return Q(), requested_fields

    # Check if operation is allowed
    allowed_ops = perm["ops"]
    if action not in allowed_ops:
        raise PermissionError(f"Access denied: operation '{action}' not allowed on '{model_name}'")

    # H5 fix: Check field depth against MAX_RELATION_DEPTH
    max_depth = flex_settings.MAX_RELATION_DEPTH
    for field in requested_fields:
        # Count the number of dots to determine nesting depth
        depth = field.count(".")
        if depth > max_depth:
            raise PermissionError(f"Field '{field}' exceeds max relation depth of {max_depth}")

    # Check if all requested fields are allowed
    allowed_fields = perm["fields"]
    is_allowed, denied_field = fields_allowed(requested_fields, allowed_fields)
    if not is_allowed:
        raise PermissionError(f"Access denied: field '{denied_field}' not accessible")

    # Determine row filter:
    # 1. Config "rows" takes precedence (allows override)
    # 2. Else use resolver's row_filter (centralized security)
    # 3. Else no filter
    row_filter_spec = perm["rows"]
    if row_filter_spec == "*":
        # "*" means all rows (no filter)
        row_filter = Q()
    elif callable(row_filter_spec):
        # Callable in config - pass user (may be None for anon)
        row_filter = row_filter_spec(user)
    elif isinstance(row_filter_spec, Q):
        # Q object directly in config (for anon role)
        row_filter = row_filter_spec
    elif row_filter_spec is not None:
        # Some other value in config
        row_filter = Q(pk=-1)  # Deny all for invalid spec
    elif resolver_row_filter is not None:
        # Use resolver's row filter (the default secure path)
        row_filter = resolver_row_filter
    else:
        # No filter specified anywhere - allow all rows
        row_filter = Q()

    return row_filter, requested_fields


def check_filter_permission(user, model_name, filter_keys, permissions=None):
    """
    Check if user can filter on the given filter keys.

    Args:
        user: Django User instance
        model_name: Model name (lowercase)
        filter_keys: List of filter keys (e.g., ["name", "status.in", "owner.name.icontains"])
        permissions: Optional permissions dict

    Raises:
        PermissionError: If filter key not allowed
    """
    if not filter_keys:
        return

    if permissions is None:
        permissions = flex_settings.PERMISSIONS

    model_name = model_name.lower()

    # Check if model is accessible
    if model_name not in permissions:
        raise PermissionError(f"Access denied: model '{model_name}' not configured")

    model_perms = permissions[model_name]

    # H3 fix: Handle anonymous users via 'anon' role
    is_anonymous = user is None or not getattr(user, "is_authenticated", False)

    if is_anonymous:
        role = "anon"
        if role not in model_perms:
            raise PermissionError(f"Anonymous access denied: no 'anon' role configured for '{model_name}'")
    else:
        # Get user's role (may return tuple, we only need role name)
        role_result = get_user_role(user, model_name, permissions)
        role = role_result[0] if isinstance(role_result, tuple) else role_result

    if not role:
        raise PermissionError("No role could be determined for user")

    # Check if role has access to this model
    if role not in model_perms:
        raise PermissionError(f"Access denied: role '{role}' cannot access '{model_name}'")

    # Normalize the role config
    perm = normalize_role_config(model_perms[role])

    # "*" means all filters allowed
    allowed_filters = perm["filters"]
    if allowed_filters == "*":
        return

    max_depth = flex_settings.MAX_RELATION_DEPTH

    for key in filter_keys:
        # Skip composite operators (or, and, not) - they're handled recursively
        if key in ("or", "and", "not"):
            continue

        # Check relation depth (without operator suffix)
        parts = key.split(".")
        depth_parts = parts[:-1] if parts[-1] in OPERATORS else parts
        if len(depth_parts) > max_depth:
            raise PermissionError(f"Filter denied: '{key}' exceeds max relation depth of {max_depth}")

        # Exact match required - operators must be explicitly granted
        if key not in allowed_filters:
            raise PermissionError(f"Filter denied: '{key}' not allowed for filtering")


def check_order_permission(user, model_name, order_by, permissions=None):
    """
    Check if user can order by the given field.

    Args:
        user: Django User instance
        model_name: Model name (lowercase)
        order_by: Order by field (e.g., "name", "-created_at", "owner.name")
        permissions: Optional permissions dict

    Raises:
        PermissionError: If order_by not allowed
    """
    if not order_by:
        return

    if permissions is None:
        permissions = flex_settings.PERMISSIONS

    model_name = model_name.lower()

    # Check if model is accessible
    if model_name not in permissions:
        raise PermissionError(f"Access denied: model '{model_name}' not configured")

    model_perms = permissions[model_name]

    # H3 fix: Handle anonymous users via 'anon' role
    is_anonymous = user is None or not getattr(user, "is_authenticated", False)

    if is_anonymous:
        role = "anon"
        if role not in model_perms:
            raise PermissionError(f"Anonymous access denied: no 'anon' role configured for '{model_name}'")
    else:
        # Get user's role (may return tuple, we only need role name)
        role_result = get_user_role(user, model_name, permissions)
        role = role_result[0] if isinstance(role_result, tuple) else role_result

    if not role:
        raise PermissionError("No role could be determined for user")

    # Check if role has access to this model
    if role not in model_perms:
        raise PermissionError(f"Access denied: role '{role}' cannot access '{model_name}'")

    # Normalize the role config
    perm = normalize_role_config(model_perms[role])

    # "*" means all order_by allowed
    allowed_order = perm["order_by"]
    if allowed_order == "*":
        return

    if order_by not in allowed_order:
        raise PermissionError(f"Order denied: '{order_by}' not allowed for ordering")
