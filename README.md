# Django-Flex

<p align="center">
    <em>A flexible query language for Django — let your frontend dynamically construct database queries</em>
</p>

<p align="center">
    <a href="https://pypi.org/project/django-flex/">
        <img src="https://img.shields.io/pypi/v/django-flex.svg" alt="PyPI version">
    </a>
    <a href="https://pypi.org/project/django-flex/">
        <img src="https://img.shields.io/pypi/pyversions/django-flex.svg" alt="Python versions">
    </a>
    <a href="https://github.com/your-org/django-flex/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
    </a>
</p>

---

**Django-Flex** enables frontends to send flexible, dynamic queries to your Django backend — think of it as a simpler alternative to GraphQL that feels native to Django.

## Features

- 🎯 **Field Selection** — Request only the fields you need, including nested relations
- 🔍 **Dynamic Filtering** — Full Django ORM operator support with composable AND/OR/NOT
- 📄 **Smart Pagination** — Limit/offset with cursor-based continuation
- 🔒 **Built-in Security** — Row-level, field-level, and operation-level permissions
- ⚡ **Automatic Optimization** — N+1 prevention with smart `select_related`
- 🐍 **Django-Native** — Feels like a natural extension of Django

## Installation

```bash
pip install django-flex
```

Add to your Django settings:

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_flex',
]

# Optional: Configure permissions and defaults
DJANGO_FLEX = {
    'DEFAULT_LIMIT': 50,
    'MAX_LIMIT': 200,
    'PERMISSIONS': {
        # See Permission Configuration below
    },
}
```

## Quick Start

### 1. Class-Based View (Recommended)

```python
# views.py
from django_flex import FlexQueryView
from myapp.models import Booking

class BookingQueryView(FlexQueryView):
    model = Booking
    
    # Define permissions for this view
    flex_permissions = {
        'authenticated': {
            'rows': lambda user: Q(team__members=user),
            'fields': ['id', 'status', 'customer.name', 'customer.email'],
            'filters': ['status', 'status.in', 'customer.name.icontains'],
            'order_by': ['created_at', '-created_at'],
            'ops': ['get', 'query'],
        },
    }
```

```python
# urls.py
from django.urls import path
from myapp.views import BookingQueryView

urlpatterns = [
    path('api/bookings/', BookingQueryView.as_view()),
    path('api/bookings/<int:pk>/', BookingQueryView.as_view()),  # Single object by ID
]
```

### 2. Make Queries from Frontend

```javascript
// List bookings with field selection and filtering
const response = await fetch('/api/bookings/', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        fields: 'id, status, customer.name, customer.email',
        filters: {
            'status.in': ['confirmed', 'completed'],
            'customer.name.icontains': 'khan'
        },
        order_by: '-created_at',
        limit: 20
    })
});

const data = await response.json();
// {
//     "pagination": {"offset": 0, "limit": 20, "has_more": true},
//     "results": {
//         "1": {"id": 1, "status": "confirmed", "customer": {"name": "Aisha Khan", "email": "aisha@example.com"}},
//         "2": {"id": 2, "status": "completed", "customer": {"name": "Omar Khan", "email": "omar@example.com"}}
//     }
// }
```

```javascript
// Get single object by ID (using URL)
const booking = await fetch('/api/bookings/1/', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        fields: 'id, status, customer.*, address.*'
    })
});
// Returns: {"id": 1, "status": "confirmed", "customer": {...}, "address": {...}}
```

## Query Language Reference

### Field Selection

```javascript
// All fields on the model
{ fields: '*' }

// Specific fields
{ fields: 'id, name, email' }

// Nested relation fields (dot notation)
{ fields: 'id, customer.name, customer.email' }

// Relation wildcards
{ fields: 'id, status, customer.*, address.*' }
```

### Filtering

```javascript
// Simple equality
{ filters: { status: 'confirmed' } }

// With operators
{ filters: { 'price.gte': 100, 'price.lte': 500 } }

// Text search
{ filters: { 'name.icontains': 'khan' } }

// List membership
{ filters: { 'status.in': ['pending', 'confirmed', 'completed'] } }

// OR conditions
{ filters: { or: { status: 'pending', 'customer.vip': true } } }

// NOT conditions  
{ filters: { not: { status: 'cancelled' } } }

// Complex composition
{
    filters: {
        'created_at.gte': '2024-01-01',
        or: [
            { status: 'confirmed' },
            { and: { status: 'pending', 'urgent': true } }
        ]
    }
}
```

**Supported Operators:**

| Category | Operators |
|----------|-----------|
| Comparison | `lt`, `lte`, `gt`, `gte`, `exact`, `iexact`, `in`, `isnull`, `range` |
| Text | `contains`, `icontains`, `startswith`, `istartswith`, `endswith`, `iendswith`, `regex`, `iregex` |
| Date/Time | `date`, `year`, `month`, `day`, `week_day`, `hour`, `minute`, `second` |

### Pagination

```javascript
{
    limit: 20,      // Number of results (default: 50, max: 200)
    offset: 0,      // Starting position
    order_by: '-created_at'  // Sort order (prefix with - for descending)
}
```

Response includes pagination info:

```javascript
{
    "pagination": {
        "offset": 0,
        "limit": 20,
        "has_more": true,
        "next": {
            "fields": "...",
            "filters": {...},
            "limit": 20,
            "offset": 20
        }
    }
}
```

## Permission Configuration

Django-Flex uses a **deny-by-default** security model. You must explicitly grant access.

```python
# settings.py
DJANGO_FLEX = {
    'PERMISSIONS': {
        'booking': {
            # Fields excluded from wildcard expansion (security)
            'exclude': ['internal_notes', 'stripe_payment_id'],
            
            # Role-based permissions
            'owner': {
                # Row-level: which rows can this role see?
                'rows': lambda user: Q(created_by=user),
                
                # Field-level: which fields can they access?
                'fields': ['*', 'customer.*', 'address.*'],
                
                # Filter-level: which fields can they filter on?
                'filters': [
                    'id', 'status', 'status.in',
                    'customer.name', 'customer.name.icontains',
                    'created_at.gte', 'created_at.lte',
                ],
                
                # Order-level: which fields can they sort by?
                'order_by': ['id', '-id', 'created_at', '-created_at', 'customer.name'],
                
                # Operation-level: which actions can they perform?
                'ops': ['get', 'query', 'create', 'update', 'delete'],
            },
            
            'staff': {
                'rows': lambda user: Q(team__members=user),
                'fields': ['id', 'status', 'customer.name', 'address.city'],
                'filters': ['status', 'status.in'],
                'order_by': ['created_at', '-created_at'],
                'ops': ['get', 'query'],
            },
            
            # Roles not listed have NO ACCESS
        },
    },
}
```

### Custom Role Resolution

Django-Flex uses Django's built-in groups for role resolution:

```python
from django_flex import FlexPermission

class MyPermission(FlexPermission):
    def get_user_role(self, user):
        if user.is_superuser:
            return 'superuser'
        if user.groups.filter(name='Managers').exists():
            return 'manager'
        return 'staff'
```

## Usage Patterns

### 1. Class-Based View (Recommended)

```python
from django_flex import FlexQueryView

class BookingQueryView(FlexQueryView):
    model = Booking
    require_auth = True
    allowed_actions = ['get', 'query']
    flex_permissions = {...}
```

### 2. Function Decorator

```python
from django_flex import flex_query
from django.http import JsonResponse

@flex_query(
    model=Booking,
    allowed_fields=['id', 'status', 'customer.name'],
    allowed_filters=['status', 'status.in'],
)
def booking_list(request, result, query_spec):
    return JsonResponse(result.to_dict())
```

### 3. Programmatic Usage

```python
from django_flex import FlexQuery

def my_view(request):
    result = FlexQuery(Booking).execute({
        'fields': 'id, customer.name',
        'filters': {'status': 'confirmed'},
        'limit': 20,
    }, user=request.user)
    
    return JsonResponse(result.to_dict())
```

### 4. Middleware (Single Endpoint)

```python
# settings.py
MIDDLEWARE = [
    ...
    'django_flex.middleware.FlexQueryMiddleware',
]

DJANGO_FLEX = {
    'MIDDLEWARE_PATH': '/api/',
    ...
}
```

Then query any configured model:

```javascript
fetch('/api/', {
    method: 'POST',
    body: JSON.stringify({
        _model: 'booking',
        _action: 'query',
        fields: 'id, status',
        limit: 20
    })
});
```

## Configuration Reference

```python
DJANGO_FLEX = {
    # Pagination
    'DEFAULT_LIMIT': 50,        # Default page size
    'MAX_LIMIT': 200,           # Maximum page size (hard cap)
    
    # Security
    'MAX_RELATION_DEPTH': 2,    # Max depth for nested fields/filters
    'REQUIRE_AUTHENTICATION': True,  # Require auth by default
    'AUDIT_QUERIES': False,     # Log all queries (for debugging)
    
    # Middleware
    'MIDDLEWARE_PATH': '/api/',  # Path for middleware endpoint
    
    # Optional: versioned APIs with independent settings
    'VERSIONS': {
        'v1': {'path': '/api/v1/', 'PERMISSIONS': {...}},
        'v2': {'path': '/api/v2/', 'PERMISSIONS': {...}},
    },
    
    # Model permissions (see Rate Limiting section below)
    'PERMISSIONS': {...},
}
```

### API Versioning

Run unversioned `/api/` alongside versioned `/api/v1/`, `/api/v2/` with different settings per version:

```python
DJANGO_FLEX = {
    'MIDDLEWARE_PATH': '/api/',  # Unversioned endpoint
    'PERMISSIONS': {...},        # Top-level = unversioned settings
    'MAX_LIMIT': 200,
    
    'VERSIONS': {
        'v1': {
            'path': '/api/v1/',
            'PERMISSIONS': {...},  # v1-specific permissions
            'MAX_LIMIT': 100,      # v1-specific limit
        },
        'v2': {
            'path': '/api/v2/',
            'PERMISSIONS': {...},  # v2-specific permissions
            'MAX_LIMIT': 200,
        },
    },
}
```

## Rate Limiting

Rate limits can be configured at multiple levels (most specific wins):

```python
DJANGO_FLEX = {
    'PERMISSIONS': {
        'booking': {
            # Model-level: integer = same for all ops
            'rate_limit': 60,
            
            # OR dict for per-operation limits
            # 'rate_limit': {'default': 60, 'query': 30, 'get': 120},
            
            # Anonymous users - very restricted
            'anon': {
                'fields': ['id', 'status'],
                'ops': ['query'],
                'rate_limit': 5,  # Only 5 requests/minute for anon
            },
            
            'authenticated': {
                'fields': ['*'],
                'ops': ['get', 'query'],
                'rate_limit': 50,
            },
            
            'staff': {
                'fields': ['*'],
                'ops': ['get', 'query'],
                'rate_limit': 200,  # Staff gets higher limits
            },
        },
    },
}
```

### Behind a Proxy

By default, anonymous rate limiting uses `REMOTE_ADDR` (not spoofable). If you are
behind a trusted reverse proxy that sets `X-Forwarded-For`, enable:

```python
DJANGO_FLEX = {
    'RATE_LIMIT_USE_FORWARDED_IP': True,
}
```

WARNING: Only enable this if your proxy is properly configured to set
`X-Forwarded-For`. Otherwise attackers can spoof their IP and bypass limits.

When rate limit is exceeded, returns HTTP 429 with `Retry-After` header:

```json
{"error": "Rate limit exceeded", "retry_after": 45}
```

## Response Format

Responses use HTTP status codes (200, 400, 401, 403, 404) to indicate success/failure.

### Successful Single Object (get) - HTTP 200

```json
{
    "id": 1,
    "status": "confirmed",
    "customer": {
        "name": "Aisha Khan",
        "email": "aisha@example.com"
    }
}
```

### Successful Query (query) - HTTP 200

```json
{
    "pagination": {
        "offset": 0,
        "limit": 20,
        "has_more": true,
        "next": {...}
    },
    "results": {
        "1": {...},
        "2": {...}
    }
}
```

### Error Response - HTTP 400/401/403/404

```json
{
    "error": "Access denied: field 'secret_field' not accessible"
}
```

## Why Django-Flex?

| Feature | Django-Flex | GraphQL | REST |
|---------|-------------|---------|------|
| Learning curve | Low (Django-native) | High | Low |
| Field selection | ✅ | ✅ | ❌ (fixed endpoints) |
| Dynamic filtering | ✅ | ✅ | Limited |
| Built-in security | ✅ | Manual | Manual |
| Django integration | Native | Requires graphene | Native |
| Schema definition | Optional | Required | N/A |
| N+1 prevention | Automatic | Manual | Manual |


## License

MIT License — see [LICENSE](LICENSE) for details.
