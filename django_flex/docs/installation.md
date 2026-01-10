# Installation Guide

This guide covers installing django-flex in your Django project.

## Requirements

- Python 3.8 or higher
- Django 3.2 or higher

## Install from PyPI

```bash
pip install django-flex
```

Or with optional development dependencies:

```bash
pip install django-flex[dev]
```

## Add to Django Settings

Add `django_flex` to your `INSTALLED_APPS`:

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Add django-flex
    'django_flex',
    
    # Your apps
    'myapp',
]
```

## Configure Django-Flex (Optional)

Add the `DJANGO_FLEX` settings dictionary to customize behavior:

```python
# settings.py
DJANGO_FLEX = {
    # Pagination defaults
    'DEFAULT_LIMIT': 50,
    'MAX_LIMIT': 200,
    
    # Security settings
    'MAX_RELATION_DEPTH': 2,
    'REQUIRE_AUTHENTICATION': True,
    
    # Model permissions (see Permissions Guide)
    'EXPOSE': {
        # Configure per-model permissions here
    },
}
```

## Verify Installation

Start your Django development server:

```bash
python manage.py runserver
```

In a Python shell, verify the import works:

```python
>>> from django_flex import FlexQuery
>>> print(FlexQuery)
<class 'django_flex.query.FlexQuery'>
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Build your first flexible query endpoint
- [Permissions Guide](permissions.md) - Configure security for your models
- [API Reference](api_reference.md) - Complete API documentation
