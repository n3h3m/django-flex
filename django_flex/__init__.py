"""
Django-Flex: Flexible Query Language for Django

A Django-native query builder that enables frontends to send JSON query
specifications to the backend, supporting field selection, filtering,
pagination, and comprehensive security controls.

Example:
    from django_flex import FlexQuery

    result = FlexQuery(Booking).execute({
        'fields': 'id, customer.name, status',
        'filters': {'status': 'confirmed'},
        'limit': 20,
    })
"""

__version__ = "26.1.3"
__author__ = "Nehemiah Jacob"

# Core query execution
from django_flex.query import FlexQuery, execute_query

# Field utilities
from django_flex.fields import (
    parse_fields,
    expand_fields,
    get_model_fields,
    get_model_relations,
    extract_relations,
)

# Filter utilities
from django_flex.filters import (
    parse_filter_key,
    build_q_object,
    extract_filter_keys,
    OPERATORS,
)

# Permissions
from django_flex.permissions import (
    FlexPermission,
    check_permission,
    check_filter_permission,
    check_order_permission,
)

# Views
from django_flex.views import FlexQueryView

# Decorators
from django_flex.decorators import flex_query

# Response utilities
from django_flex.response import FlexResponse, build_nested_response

# Configuration
from django_flex.conf import flex_settings

__all__ = [
    # Version
    "__version__",
    # Query
    "FlexQuery",
    "execute_query",
    # Fields
    "parse_fields",
    "expand_fields",
    "get_model_fields",
    "get_model_relations",
    "extract_relations",
    # Filters
    "parse_filter_key",
    "build_q_object",
    "extract_filter_keys",
    "OPERATORS",
    # Permissions
    "FlexPermission",
    "check_permission",
    "check_filter_permission",
    "check_order_permission",
    # Views
    "FlexQueryView",
    # Decorators
    "flex_query",
    # Response
    "FlexResponse",
    "build_nested_response",
    # Settings
    "flex_settings",
]
