"""
Pytest configuration and shared fixtures for CalibraWeb testing
"""
import pytest
import os
import uuid
from django.contrib.auth.models import User
from django.test import Client
from unittest.mock import patch

from organization.models import Setor
from rh.models import Colaborador

# Disable 2FA for testing
os.environ['TESTING'] = 'True'


@pytest.fixture
def client():
    """Django test client fixture"""
    return Client()


@pytest.fixture
def user(db):
    """Create a test user with unique username and skip 2FA requirement"""
    unique_username = f'testuser_{uuid.uuid4().hex[:8]}'
    user_obj = User.objects.create_user(
        username=unique_username,
        password='testpass123',
        email='test@example.com'
    )
    # Mark OTP as verified to skip 2FA setup
    try:
        from django_otp.models import StaticDevice, StaticToken
        # Create a static OTP device for the user
        device = StaticDevice.objects.create(user=user_obj, name='Static', confirmed=True)
        # Create a token
        StaticToken.objects.create(device=device, token='000000')
    except Exception:
        pass
    return user_obj



@pytest.fixture
def authenticated_client(client, user):
    """Create an authenticated test client"""
    client.force_login(user)
    return client


@pytest.fixture
def setor():
    """Create a test Setor"""
    return Setor.objects.create(
        nome="Setor Teste",
        responsavel="Responsável Teste"
    )


@pytest.fixture
def colaborador(user, setor):
    """Create a test Colaborador"""
    return Colaborador.objects.create(
        user=user,
        matricula="MAT-TEST",
        cpf="12345678901",
        nome_completo="Colaborador Teste",
        cargo="Desenvolvedor",
        setor=setor,
        salario=5000.00,
        is_active=True
    )


@pytest.fixture(scope='session', autouse=True)
def django_db_setup(django_db_setup, django_db_blocker):
    """Setup Django database for tests"""
    with django_db_blocker.unblock():
        from django.core.management import call_command
        call_command('migrate', '--run-syncdb', verbosity=0)


@pytest.fixture(autouse=True)
def mock_2fa(settings):
    """Disable 2FA for all tests automatically"""
    # Disable 2FA patch for admin
    settings.TWO_FACTOR_PATCH_ADMIN = False
    
    # Set LOGIN_URL to a simple login page (not 2FA)
    settings.LOGIN_URL = 'admin:login'
    
    # Remove 2FA from middleware if it exists
    if 'two_factor.middleware.ThreadLocalMiddleware' in settings.MIDDLEWARE:
        settings.MIDDLEWARE = list(settings.MIDDLEWARE)
        settings.MIDDLEWARE.remove('two_factor.middleware.ThreadLocalMiddleware')


@pytest.fixture(autouse=True)
def reset_sequences(db):
    """Reset database sequences before each test"""
    from django.db import connection
    if connection.vendor == 'sqlite':
        pass  # SQLite doesn't need sequence reset
