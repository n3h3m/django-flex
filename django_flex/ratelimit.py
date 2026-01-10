"""
Django-Flex Rate Limiting

Provides multi-level rate limiting for API requests.

Rate limits are configured as integers (requests per minute) at multiple levels:
- Global: DJANGO_FLEX['rate_limit']
- Model-level: PERMISSIONS['model']['rate_limit']
- Role-level: PERMISSIONS['model']['role']['rate_limit']

Values can be:
- Integer: Same limit for all operations
- Dict: Per-operation limits (e.g., {'default': 50, 'list': 20})
"""

import time

from django.core.cache import cache

from django_flex.conf import flex_settings


def get_rate_limit_key(user_id, model_name, action):
    """
    Build cache key for rate limiting.

    Args:
        user_id: User's primary key
        model_name: Model name (lowercase)
        action: Action name (get, query, etc.)

    Returns:
        Cache key string
    """
    # Use minute-based window
    minute = int(time.time() // 60)
    return f"flex_rate:{user_id}:{model_name}:{action}:{minute}"


def resolve_rate_limit(model_name, role, action, permissions=None):
    """
    Resolve the applicable rate limit for a request.

    Resolution order (most specific wins):
    1. Role + Model + Action
    2. Role + Model default
    3. Model + Action
    4. Model default
    5. Global rate_limit

    Args:
        model_name: Model name (lowercase)
        role: User's role
        action: Action being performed
        permissions: Optional permissions config

    Returns:
        Rate limit (int) or None if no limit
    """
    if permissions is None:
        permissions = flex_settings.PERMISSIONS

    model_name = model_name.lower()
    global_limit = getattr(flex_settings, "rate_limit", None)

    # Check if model exists in permissions
    if model_name not in permissions:
        return global_limit

    model_perms = permissions[model_name]

    # 1. Try role-specific limit
    if role and role in model_perms:
        role_perms = model_perms[role]
        role_limit = role_perms.get("rate_limit")

        if role_limit is not None:
            if isinstance(role_limit, dict):
                # Try action-specific, then default
                if action in role_limit:
                    return role_limit[action]
                if "default" in role_limit:
                    return role_limit["default"]
            else:
                # Integer = same for all ops
                return role_limit

    # 2. Try model-level limit
    model_limit = model_perms.get("rate_limit")

    if model_limit is not None:
        if isinstance(model_limit, dict):
            # Try action-specific, then default
            if action in model_limit:
                return model_limit[action]
            if "default" in model_limit:
                return model_limit["default"]
        else:
            # Integer = same for all ops
            return model_limit

    # 3. Fall back to global
    return global_limit


def check_rate_limit(user, model_name, action, permissions=None, request=None):
    """
    Check if request is within rate limit.

    Args:
        user: Django User instance (or None for anon)
        model_name: Model name (lowercase)
        action: Action being performed
        permissions: Optional permissions config
        request: Optional Django request (for IP-based anon tracking)

    Returns:
        Tuple of (allowed, retry_after)
        - allowed: True if request is allowed
        - retry_after: Seconds until limit resets (0 if allowed)
    """
    # Superusers bypass rate limits
    if user and user.is_authenticated and user.is_superuser:
        return True, 0

    # Get user's role (may return tuple, we only need role name)
    from django_flex.permissions import get_user_role

    role_result = get_user_role(user, model_name, permissions)
    role = role_result[0] if isinstance(role_result, tuple) else role_result

    # Resolve applicable limit
    limit = resolve_rate_limit(model_name, role, action, permissions)

    if limit is None:
        # No rate limit configured
        return True, 0

    # Build cache key - use user.pk for authenticated, IP for anon
    if user and user.is_authenticated:
        identifier = str(user.pk)
    elif request:
        # Use IP address for anonymous users
        identifier = _get_client_ip(request)
    else:
        # No user, no request - can't track, allow through
        return True, 0

    key = get_rate_limit_key(identifier, model_name, action)

    # Get current count
    current = cache.get(key, 0)

    if current >= limit:
        # Calculate retry_after (seconds until next minute)
        seconds_into_minute = int(time.time()) % 60
        retry_after = 60 - seconds_into_minute
        return False, retry_after

    # Increment counter
    try:
        cache.incr(key)
    except ValueError:
        # Key doesn't exist, create it
        cache.set(key, 1, timeout=60)

    return True, 0


def _get_client_ip(request):
    """Get client IP address for rate limiting.

    By default, uses REMOTE_ADDR which cannot be spoofed by the client.
    Set RATE_LIMIT_USE_FORWARDED_IP=True only when behind a trusted proxy.
    """
    if flex_settings.RATE_LIMIT_USE_FORWARDED_IP:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after=60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")
