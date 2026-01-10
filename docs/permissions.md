# Permissions Guide

Django-Flex uses a **deny-by-default** security model. Users have no access unless explicitly granted.

## Django Auth Integration

Django-Flex integrates natively with Django's built-in auth system:

- **User.is_superuser** → bypasses all permission checks
- **User.is_staff** → gets `staff` role
- **User.groups** → first group name becomes the role
- **Authenticated (no group)** → gets `authenticated` role

### Role Resolution Order

```python
# How django-flex determines user role:
if user.is_superuser:
    role = "superuser"  # Bypasses ALL checks
elif user.is_staff:
    role = "staff"
elif user.groups.exists():
    role = user.groups.first().name.lower()
else:
    role = "authenticated"
```

## Permission Layers

Django-Flex enforces security at four levels:

1. **Row-Level** — Which database rows can the user see?
2. **Field-Level** — Which fields can the user access on those rows?
3. **Filter-Level** — Which fields can the user filter on?
4. **Operation-Level** — Which actions (get, query, create, update, delete) can the user perform?

## Configuration Structure

```python
# settings.py
DJANGO_FLEX = {
    'PERMISSIONS': {
        '<model_name>': {
            # Fields excluded from wildcard expansion (security)
            'exclude': ['password_hash', 'api_secret'],

            '<role_name>': {
                'rows': <callable returning Q object>,
                'fields': [<list of field patterns>],
                'filters': [<list of allowed filter keys>],
                'order_by': [<list of allowed order values>],
                'ops': [<list of allowed operations>],
            },
            # More roles...
        },
        # More models...
    },
}
```

## Row-Level Security

The `rows` key is a callable that receives the user and returns a Django `Q` object.

```python
from django.db.models import Q

DJANGO_FLEX = {
    'PERMISSIONS': {
        'article': {
            'staff': {
                # Staff see all articles
                'rows': lambda user: Q(),
                # ...
            },
            'authenticated': {
                # Authenticated users see only published articles
                'rows': lambda user: Q(status='published'),
                # ...
            },
        },
        'profile': {
            'authenticated': {
                # Users can only see their own profile
                'rows': lambda user: Q(user=user),
                # ...
            },
        },
    },
}
```

### Example: Multi-Tenant Isolation

```python
'rows': lambda user: Q(tenant=user.profile.tenant)
```

### Example: Team-Based Access

```python
'rows': lambda user: Q(team__in=user.teams.all())
```

## Field-Level Security

The `fields` list uses pattern matching:

| Pattern | Matches | Example |
|---------|---------|---------|
| `*` | All direct fields on model | `id`, `name`, `status` |
| `<field>` | Exact field name | `id`, `status` |
| `<relation>.*` | All fields on related model | `author.id`, `author.name` |
| `<relation>.<field>` | Specific field on related model | `author.name` |

```python
'staff': {
    # Can access everything including nested relations
    'fields': ['*', 'author.*', 'category.*'],
    # ...
},
'authenticated': {
    # Limited access - specific fields only
    'fields': ['id', 'title', 'content', 'author.name'],
    # ...
},
```

### Excluding Sensitive Fields

Use the `exclude` key to prevent fields from being exposed via wildcards:

```python
'user': {
    'exclude': ['password', 'api_key', 'secret_token'],

    'staff': {
        'fields': ['*'],  # Even with *, excluded fields won't be returned
        # ...
    },
}
```

## Filter-Level Security

The `filters` list specifies which fields can be used in the `filters` clause:

```python
'staff': {
    'filters': [
        # Direct field filters
        'id',
        'status',
        'status.in',           # Can use 'in' operator
        'status.iexact',       # Can use case-insensitive match

        # Date filters with operators
        'created_at',
        'created_at.gte',      # Can filter >= date
        'created_at.lte',      # Can filter <= date

        # Nested field filters
        'author.id',
        'author.name',
        'author.name.icontains',  # Can search by name
    ],
    # ...
},
```

**Important**: If a filter key isn't listed, users get a permission error when trying to use it.

## Order-Level Security

The `order_by` list specifies which orderings are allowed:

```python
'authenticated': {
    'order_by': [
        'id', '-id',                    # Ascending and descending
        'created_at', '-created_at',
        'title', '-title',
    ],
    # ...
},
```

**Important**: Include both ascending and descending variants if you want to allow both directions.

## Operation-Level Security

The `ops` list specifies which operations the role can perform:

| Operation | Description |
|-----------|-------------|
| `get` | Retrieve single object by ID |
| `query` | Query multiple objects with filters |
| `create` | Create new objects |
| `update` | Update existing objects |
| `delete` | Delete objects |

```python
'staff': {
    'ops': ['get', 'query', 'create', 'update', 'delete'],  # Full access
},
'authenticated': {
    'ops': ['get', 'query'],  # Read-only
},
# Roles not listed have NO ACCESS AT ALL
```

## Rate Limiting

Rate limits can be defined globally, per model, or per role using the
`rate_limit` key (requests per minute). Anonymous users are tracked by IP.

By default, django-flex uses `REMOTE_ADDR` for anonymous rate limiting to avoid
IP spoofing. If you are behind a trusted reverse proxy that sets
`X-Forwarded-For`, enable forwarded IPs:

```python
DJANGO_FLEX = {
    'RATE_LIMIT_USE_FORWARDED_IP': True,
    'PERMISSIONS': {
        'booking': {
            'rate_limit': 60,
            'anon': {
                'ops': ['query'],
                'fields': ['id', 'status'],
                'rate_limit': 5,
            },
        },
    },
}
```

WARNING: Only enable `RATE_LIMIT_USE_FORWARDED_IP` if your proxy is configured
to set `X-Forwarded-For`. Otherwise attackers can spoof their IP and bypass
rate limits.

## Complete Example

```python
# settings.py
from django.db.models import Q

DJANGO_FLEX = {
    'DEFAULT_LIMIT': 50,
    'MAX_LIMIT': 200,
    'MAX_RELATION_DEPTH': 2,

    'PERMISSIONS': {
        # =====================
        # ARTICLE MODEL
        # =====================
        'article': {
            'exclude': ['draft_content', 'internal_notes'],

            'staff': {
                'rows': lambda user: Q(),  # All articles
                'fields': ['*', 'author.*', 'category.*'],
                'filters': [
                    'id', 'status', 'status.in',
                    'created_at.gte', 'created_at.lte',
                    'author.id', 'author.name.icontains',
                    'category.id', 'category.name',
                ],
                'order_by': ['id', '-id', 'created_at', '-created_at', 'title', '-title'],
                'ops': ['get', 'query', 'create', 'update', 'delete'],
            },
            'authenticated': {
                'rows': lambda user: Q(status='published'),  # Only published
                'fields': ['id', 'title', 'content', 'author.name', 'category.name'],
                'filters': [
                    'id', 'category.id',
                    'title.icontains',
                ],
                'order_by': ['created_at', '-created_at', 'title'],
                'ops': ['get', 'query'],
            },
        },

        # =====================
        # USER PROFILE MODEL
        # =====================
        'profile': {
            'exclude': ['ssn', 'internal_id'],

            'staff': {
                'rows': lambda user: Q(),
                'fields': ['*'],
                'filters': ['id', 'user.id', 'user.email.icontains'],
                'order_by': ['id', 'created_at', '-created_at'],
                'ops': ['get', 'query', 'update'],
            },
            'authenticated': {
                'rows': lambda user: Q(user=user),  # Own profile only
                'fields': ['id', 'bio', 'avatar', 'user.email'],
                'filters': ['id'],
                'order_by': [],
                'ops': ['get', 'update'],
            },
        },

        # =====================
        # COMMENT MODEL  
        # =====================
        'comment': {
            'staff': {
                'rows': lambda user: Q(),
                'fields': ['*', 'author.*', 'article.*'],
                'filters': ['id', 'article.id', 'author.id', 'created_at.gte'],
                'order_by': ['created_at', '-created_at'],
                'ops': ['get', 'query', 'create', 'update', 'delete'],
            },
            'authenticated': {
                'rows': lambda user: Q(article__status='published'),
                'fields': ['id', 'content', 'author.name', 'created_at'],
                'filters': ['article.id'],
                'order_by': ['-created_at', 'created_at'],
                'ops': ['get', 'query', 'create'],
            },
        },
    },
}
```

## Setting Up Django Groups

Django-Flex uses Django's built-in groups for roles:

```python
# Create groups in a migration or management command
from django.contrib.auth.models import Group

Group.objects.get_or_create(name='Staff')
Group.objects.get_or_create(name='Editor')
Group.objects.get_or_create(name='Viewer')

# Assign user to a group
user.groups.add(Group.objects.get(name='Editor'))
```

Then configure permissions for these group names:

```python
DJANGO_FLEX = {
    'PERMISSIONS': {
        'article': {
            'staff': {...},     # Users in "Staff" group
            'editor': {...},    # Users in "Editor" group  
            'viewer': {...},    # Users in "Viewer" group
            'authenticated': {...},  # Logged in users with no group
        },
    },
}
```

## Security Best Practices

1. **Start Restrictive** — Begin with minimal permissions and expand as needed
2. **Use Exclude** — Always exclude sensitive fields from wildcard expansion
3. **Limit Relation Depth** — Set `MAX_RELATION_DEPTH` to prevent deep traversal
4. **Use Django Groups** — Leverage Django's built-in group system for role management
5. **Test Permissions** — Write tests that verify permission denials, not just grants
