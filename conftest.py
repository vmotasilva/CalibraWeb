"""
Pytest configuration and shared fixtures for CalibraWeb testing
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from organization.models import Setor
from rh.models import Colaborador


@pytest.fixture
def client():
    """Django test client fixture"""
    return Client()


@pytest.fixture
def user():
    """Create a test user"""
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )


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


@pytest.fixture(scope='session')
def django_db_setup():
    """Configure Django test database"""
    pass


@pytest.fixture(autouse=True)
def reset_sequences(db):
    """Reset database sequences before each test"""
    from django.db import connection
    if connection.vendor == 'sqlite':
        pass  # SQLite doesn't need sequence reset
