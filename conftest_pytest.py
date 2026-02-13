"""
Pytest configuration and shared fixtures for CalibraWeb tests
"""

import os
import django
import pytest
from django.conf import settings

# Configure Django settings for tests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibraweb.settings')

@pytest.fixture(scope='session')
def django_db_setup():
    """Setup Django database for testing"""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


@pytest.fixture
def client():
    """Provide Django test client"""
    from django.test import Client
    return Client()


# Pytest configuration
pytest_plugins = [
    'pytest_django',
]
