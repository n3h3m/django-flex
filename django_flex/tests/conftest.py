"""
Pytest configuration for django-flex tests.
"""

import os
import sys

# Add the package root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure():
    """Configure Django settings before tests run."""
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            SECRET_KEY="test-secret-key",
            DEBUG=True,
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django_flex",
            ],
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            DJANGO_FLEX={
                "DEFAULT_LIMIT": 50,
                "MAX_LIMIT": 200,
                "MAX_RELATION_DEPTH": 2,
                "PERMISSIONS": {},
            },
        )

    import django

    django.setup()
