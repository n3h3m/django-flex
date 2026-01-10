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

- **Field Selection** — Request only the fields you need, including nested relations
- **JSONField Support** — Seamless dot notation for nested JSON data
- **Dynamic Filtering** — Full Django ORM operator support with composable AND/OR/NOT
- **Smart Pagination** — Limit/offset with cursor-based continuation
- **Built-in Security** — Row-level, field-level, and operation-level permissions
- **Automatic Optimization** — N+1 prevention with smart `select_related`
- **Django-Native** — Feels like a natural extension of Django

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
    'ALWAYS_HTTP_200': False,  # When True, all responses return HTTP 200
    'EXPOSE': {
        # See Permission Configuration below
    },
}
```

### Response Modes

By default, django-flex uses standard HTTP status codes (200, 400, 404, etc.).

Set `ALWAYS_HTTP_200 = True` to always return HTTP 200 with the status code in the payload:

```python
# settings.py
DJANGO_FLEX = {
    'ALWAYS_HTTP_200': True,  # All responses return HTTP 200
}
```

**When `ALWAYS_HTTP_200 = True`:**

```json
// HTTP 200 (always)
{"status_code": 404, "error": "Object not found"}
{"status_code": 200, "id": 1, "name": "Test"}
```

**When `ALWAYS_HTTP_200 = False` (default):**

```json
// HTTP 404
{"error": "Object not found"}

// HTTP 200
{"id": 1, "name": "Test"}
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
            'ops': ['get', 'list'],
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
// List bookings with field selection and filtering (JSON body)
const response = await fetch('/api/bookings/', {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        fields: 'id, status, customer.name, customer.email',
        filters: {
            'status.in': ['confirmed', 'completed'],
            'customer.name.icontains': 'khan',
        },
        order_by: '-created_at',
        limit: 20,
    }),
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

### 3. Query Params (Alternative)

Query params can be used instead of JSON body. Query params **override** body params.

```
GET /api/bookings/?fields=id,status,customer.name&filters.status=confirmed&filters.customer.name.icontains=khan&order_by=-created_at&limit=20
```

Equivalent to:

```javascript
{
    fields: 'id, status, customer.name',
    filters: { status: 'confirmed', 'customer.name.icontains': 'khan' },
    order_by: '-created_at',
    limit: 20
}
```

| Query Param                   | Body Equivalent                         |
| ----------------------------- | --------------------------------------- |
| `fields=id,name`              | `{fields: 'id, name'}`                  |
| `limit=20`                    | `{limit: 20}`                           |
| `offset=10`                   | `{offset: 10}`                          |
| `order_by=-created_at`        | `{order_by: '-created_at'}`             |
| `filters.status=pending`      | `{filters: {status: 'pending'}}`        |
| `filters.name.icontains=khan` | `{filters: {'name.icontains': 'khan'}}` |

```javascript
// Get single object by ID (using URL)
const booking = await fetch('/api/bookings/1/', {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        fields: 'id, status, customer.*, address.*',
    }),
});
// Returns: {"id": 1, "status": "confirmed", "customer": {...}, "address": {...}}
```

## Query Language Reference

### Field Selection

```javascript
// All fields on the model
{
    fields: '*';
}

// Specific fields
{
    fields: 'id, name, email';
}

// Nested relation fields (dot notation)
{
    fields: 'id, customer.name, customer.email';
}

// Relation wildcards
{
    fields: 'id, status, customer.*, address.*';
}
```

### JSONField Support

Django-Flex seamlessly supports `JSONField` — the frontend uses the same dot notation without knowing the difference between relations and JSON keys:

```javascript
// Assume Customer model has: metadata = JSONField(default=dict)
// metadata = {"settings": {"theme": "dark", "lang": "en"}, "tags": ["vip"]}

// Select nested JSON values (same syntax as relations)
{ fields: 'name, metadata.settings.theme, metadata.tags' }
// Returns: {"name": "Alice", "metadata": {"settings": {"theme": "dark"}, "tags": ["vip"]}}

// Select entire JSONField
{ fields: 'name, metadata' }
// Returns: {"name": "Alice", "metadata": {"settings": {...}, "tags": [...]}}

// Filter on nested JSON values
{ filters: { 'metadata.settings.theme': 'dark' } }

// With operators (all Django operators work)
{
    filters: {
        'metadata.level.gte': 5,
        'metadata.tags.icontains': 'vip'
    }
}
```

**How it works:** Dot notation is transparently converted to Django's double-underscore format, which works for both ForeignKey relations AND JSONField nested keys.

**Permissions:** JSONField paths work with the same permission patterns:

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'customer': {
            'staff': {
                'fields': [
                    'name',
                    'metadata',              # Entire JSONField
                    'metadata.settings',     # Specific key
                    'metadata.settings.*',   # All keys under settings (any depth)
                ],
                'filters': [
                    'metadata.settings.theme',
                    'metadata.level',
                ],
            }
        }
    }
}
```

### ForeignKey Interchangeability

ForeignKey fields work interchangeably with integer IDs — no need to pass full objects or deal with Django's internal representations.

**Core Principle: `company` = `company_id`**

```javascript
// Creating with FK as integer - just works!
{ _model: 'service', _action: 'add', company: 1, name: 'Deep Cleaning', price: '120' }
// ✅ Django-Flex converts company: 1 → company_id: 1 internally

// Reading: 'company' returns the raw FK ID from the database
{ fields: 'id, name, company' }
// Returns: {"id": 1, "name": "Deep Cleaning", "company": 1}  (integer, no object fetch!)

// Expanding: Only fetches related object when explicitly requested
{ fields: 'id, name, company.name, company.address' }
// Returns: {"id": 1, "name": "Deep Cleaning", "company": {"name": "Acme Corp", "address": "..."}}
```

**Benefits:**

- **Efficient**: Requesting `company` returns the raw `company_id` column — no database join
- **Simple**: Pass FK values as integers directly
- **Explicit**: Related objects only fetched when you explicitly request nested fields

This applies to all CRUD operations (`add`, `edit`, `get`, `list`).

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
{ filters: {
    not: {
        status: 'cancelled'
        }
    }
}

// Complex composition
{
    filters: {
        'created_at.gte': '2024-01-01',
        or: {
            status: 'confirmed' ,
            and: {
                status: 'pending',
                urgent: true
            }
        }
    }
}
```

**Supported Operators:**

| Category   | Operators                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------ |
| Comparison | `lt`, `lte`, `gt`, `gte`, `exact`, `iexact`, `in`, `isnull`, `range`                             |
| Text       | `contains`, `icontains`, `startswith`, `istartswith`, `endswith`, `iendswith`, `regex`, `iregex` |
| Date/Time  | `date`, `year`, `month`, `day`, `week_day`, `hour`, `minute`, `second`                           |

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

Django-Flex uses a **strict deny-by-default** security model. Nothing is allowed unless explicitly granted.

### Quick Reference

| Config Value             | Meaning                     |
| ------------------------ | --------------------------- |
| `"*"`                    | **Allow all** (full access) |
| `{}`, `[]`, `""`, `None` | **Deny all** (no access)    |

### The `"*"` Shorthand

Use `"*"` to grant full access to a role:

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'user': {
            'superuser': '*',  # Full access to everything
        },
        'booking': {
            'admin': '*',      # Full access to bookings
            'staff': {...},    # Explicit permissions
        },
    },
}
```

The `"*"` shorthand expands to:

```python
{
    'rows': '*',      # All rows (no filter)
    'fields': ['*'],  # All fields including nested
    'filters': '*',   # All filters
    'order_by': '*',  # All order_by
    'ops': ['get', 'list', 'add', 'edit', 'delete'],
}
```

### Explicit Permissions

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'booking': {
            # Fields excluded from wildcard expansion
            'exclude': ['internal_notes', 'stripe_payment_id'],

            'owner': {
                # Row-level: which rows can this role see?
                'rows': lambda user: Q(created_by=user),

                # Field-level: which fields can they access?
                # "*" matches ALL fields including nested
                'fields': ['*'],

                # Filter-level: EACH filter+operator must be listed
                'filters': [
                    'status',              # Only exact: status=X
                    'status.in',           # status.in=[A,B]
                    'status.icontains',    # status.icontains=X
                    'created_at.gte',      # created_at.gte=DATE
                    'created_at.lte',      # created_at.lte=DATE
                ],

                # Order-level: which fields can they sort by?
                'order_by': ['created_at', '-created_at'],

                # Operation-level: which actions?
                'ops': ['get', 'list'],
            },

            # Empty config = NO ACCESS
            'viewer': {},

            # Roles not listed = NO ACCESS
        },
    },
}
```

> **Important**: Filters require explicit operator grants. `'status'` does NOT auto-allow `'status.in'` or `'status.gte'`. Each must be listed separately.

### Custom Role Resolution (ROLE_RESOLVER)

By default, Django-Flex resolves roles using Django's built-in auth system (superuser → staff → groups → authenticated → anon).

For custom logic, configure `ROLE_RESOLVER` — a callable that takes `(user, model_name)` and returns either:

- **String**: Just the role name
- **Tuple**: `(role_name, row_filter)` for centralized row-level security

```python
# settings.py
from django.db.models import Q

def my_role_resolver(user, model_name):
    """Custom role resolver with row-level security."""
    if not user.is_authenticated:
        return 'anon'

    # Get user's company membership
    membership = user.company_memberships.filter(is_active=True).first()
    if not membership:
        return 'authenticated'

    # Return role AND row filter (centralized security)
    company_filter = Q(company_id=membership.company_id)

    if membership.role == 'admin':
        return ('admin', company_filter)
    elif membership.role == 'staff':
        return ('staff', company_filter)
    else:
        return ('viewer', company_filter)

DJANGO_FLEX = {
    'ROLE_RESOLVER': my_role_resolver,
    'EXPOSE': {
        'booking': {
            'admin': {
                'fields': ['*'],
                'ops': ['get', 'list', 'add', 'edit', 'delete'],
                # No 'rows' needed — resolver provides it!
            },
            'staff': {
                'fields': ['id', 'status', 'customer.name'],
                'ops': ['get', 'list'],
                # No 'rows' needed — resolver provides it!
            },
        },
    },
}
```

**Row Filter Precedence:**

1. Config `rows` (if specified) — overrides resolver
2. Resolver's row_filter — used if no config `rows`
3. No filter — all rows allowed

This allows centralized, model-agnostic row security while still permitting per-model overrides when needed.

## Usage Patterns

### 1. Class-Based View (Recommended)

```python
from django_flex import FlexQueryView

class BookingQueryView(FlexQueryView):
    model = Booking
    require_auth = True
    allowed_actions = ['get', 'list']
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

The middleware supports **two styles** of API access:

#### Style A: JSON Body (Single Endpoint)

All requests go to `/api/` with model and action in the body:

```javascript
fetch('/api/', {
    method: 'POST',
    body: JSON.stringify({
        _model: 'booking',
        _action: 'list',
        fields: 'id, status',
        limit: 20,
    }),
});
```

#### Style B: RESTful URLs (Recommended)

Use standard REST patterns with HTTP method mapping:

```bash
# Query all bookings (GET → query action)
curl http://localhost:8000/api/bookings/

# Get single booking by ID (GET with ID → get action)
curl http://localhost:8000/api/bookings/1

# Create booking (POST → create action)
curl -X POST http://localhost:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "status": "pending"}'

# Update booking (PUT/PATCH → update action)
curl -X PUT http://localhost:8000/api/bookings/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "confirmed"}'

# Delete booking (DELETE → delete action)
curl -X DELETE http://localhost:8000/api/bookings/1
```

**HTTP Method Mapping:**

| Method    | URL Pattern         | Action   |
| --------- | ------------------- | -------- |
| GET       | `/api/{model}/`     | `query`  |
| GET       | `/api/{model}/{id}` | `get`    |
| POST      | `/api/{model}/`     | `create` |
| PUT/PATCH | `/api/{model}/{id}` | `update` |
| DELETE    | `/api/{model}/{id}` | `delete` |

You can still pass query options in the body for RESTful requests:

```javascript
// GET /api/bookings/ with body for filtering
fetch('/api/bookings/', {
    method: 'GET',
    body: JSON.stringify({
        fields: 'id, status, customer.name',
        filters: { status: 'confirmed' },
        limit: 20,
    }),
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

    # Response behavior
    'ALWAYS_HTTP_200': False,   # When True, all responses return HTTP 200

    # Role resolution
    'ROLE_RESOLVER': None,      # Optional: callable(user, model_name) -> str or (str, Q)

    # Middleware
    'MIDDLEWARE_PATH': '/api/',  # Path for middleware endpoint

    # Optional: versioned APIs with independent settings
    'VERSIONS': {
        'v1': {'path': '/api/v1/', 'EXPOSE': {...}},
        'v2': {'path': '/api/v2/', 'EXPOSE': {...}},
    },

    # Model permissions (see Permission Configuration above)
    'EXPOSE': {...},
}
```

### API Versioning

Run unversioned `/api/` alongside versioned `/api/v1/`, `/api/v2/` with different settings per version:

```python
DJANGO_FLEX = {
    'MIDDLEWARE_PATH': '/api/',  # Unversioned endpoint
    'EXPOSE': {...},        # Top-level = unversioned settings
    'MAX_LIMIT': 200,

    'VERSIONS': {
        'v1': {
            'path': '/api/v1/',
            'EXPOSE': {...},  # v1-specific permissions
            'MAX_LIMIT': 100,      # v1-specific limit
        },
        'v2': {
            'path': '/api/v2/',
            'EXPOSE': {...},  # v2-specific permissions
            'MAX_LIMIT': 200,
        },
    },
}
```

## Rate Limiting

Rate limits can be configured at multiple levels (most specific wins):

```python
DJANGO_FLEX = {
    'EXPOSE': {
        'booking': {
            # Model-level: integer = same for all ops
            'rate_limit': 60,

            # OR dict for per-operation limits
            # 'rate_limit': {'default': 60, 'list': 30, 'get': 120},

            # Anonymous users - very restricted
            'anon': {
                'fields': ['id', 'status'],
                'ops': ['list'],
                'rate_limit': 5,  # Only 5 requests/minute for anon
            },

            'authenticated': {
                'fields': ['*'],
                'ops': ['get', 'list'],
                'rate_limit': 50,
            },

            'staff': {
                'fields': ['*'],
                'ops': ['get', 'list'],
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
{ "error": "Rate limit exceeded", "retry_after": 45 }
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

| Feature            | Django-Flex         | GraphQL           | REST                 |
| ------------------ | ------------------- | ----------------- | -------------------- |
| Learning curve     | Low (Django-native) | High              | Low                  |
| Field selection    | ✅                  | ✅                | ❌ (fixed endpoints) |
| Dynamic filtering  | ✅                  | ✅                | Limited              |
| Built-in security  | ✅                  | Manual            | Manual               |
| Django integration | Native              | Requires graphene | Native               |
| Schema definition  | Optional            | Required          | N/A                  |
| N+1 prevention     | Automatic           | Manual            | Manual               |

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.
