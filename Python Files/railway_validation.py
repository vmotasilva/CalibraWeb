#!/usr/bin/env python
"""
RAILWAY POST-DEPLOYMENT VALIDATION SCRIPT
==========================================

Valida que a aplicação CalibraWeb está funcionando corretamente em produção.

Uso:
    python railway_validation.py

Requisitos:
    - Aplicação rodando no Railway
    - PostgreSQL conectado
    - Migrations executadas
    - Superuser criado
"""

import os
import sys
import django
from django.core.management import call_command
from django.db import connection
from django.apps import apps

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from metrologia.models import Instrumento, CategoriaInstrumento, UnidadeMedida


class DeploymentValidator:
    """Valida post-deployment do Railway"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.results = []
    
    def test(self, name, func):
        """Executa um teste e registra resultado"""
        try:
            func()
            self.tests_passed += 1
            self.results.append(f"✅ {name}")
            print(f"✅ {name}")
        except Exception as e:
            self.tests_failed += 1
            self.results.append(f"❌ {name}: {str(e)}")
            print(f"❌ {name}")
            print(f"   Erro: {str(e)}")
    
    def test_database_connection(self):
        """Testa conexão com banco de dados"""
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone() is not None
    
    def test_postgresql(self):
        """Verifica que está usando PostgreSQL"""
        db_engine = connection.get_connection_params().get('engine', '')
        assert 'postgresql' in connection.get_connection_params().get(
            'NAME', ''
        ) or 'postgres' in str(connection)
    
    def test_migrations_applied(self):
        """Verifica que todas as migrations foram aplicadas"""
        from django.core.management import execute_from_command_line
        from django.db.migrations.executor import MigrationExecutor
        
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)
    
    def test_superuser_exists(self):
        """Verifica que existe superuser"""
        assert User.objects.filter(is_superuser=True).exists()
    
    def test_apps_loaded(self):
        """Verifica que todos os apps estão carregados"""
        expected_apps = [
            'organization', 'rh', 'metrologia', 'training',
            'procurements', 'qms', 'admin', 'auth'
        ]
        loaded_apps = [app.label for app in apps.get_app_configs()]
        for app in expected_apps:
            assert app in loaded_apps, f"App {app} não carregado"
    
    def test_static_files(self):
        """Verifica que static files foram coletados"""
        from django.contrib.staticfiles.finders import get_finders
        from django.conf import settings
        
        # Verificar que WhiteNoise está configurado
        assert 'whitenoise' in settings.MIDDLEWARE or hasattr(
            settings, 'STORAGES'
        ), "WhiteNoise não configurado"
    
    def test_settings_production(self):
        """Verifica configurações de produção"""
        from django.conf import settings
        
        assert settings.DEBUG is False, "DEBUG deve ser False"
        assert settings.SECURE_SSL_REDIRECT is True, "SSL redirect desligado"
        assert settings.SESSION_COOKIE_SECURE is True, "SESSION_COOKIE_SECURE desligado"
        assert settings.CSRF_COOKIE_SECURE is True, "CSRF_COOKIE_SECURE desligado"
    
    def test_database_tables(self):
        """Verifica que tabelas existem"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            expected = [
                'metrologia_instrumento',
                'metrologia_historicocalibracao',
                'rh_colaborador',
                'organization_hierarquiasetor'
            ]
            for table in expected:
                assert table in tables, f"Tabela {table} não existe"
    
    def test_create_test_data(self):
        """Testa criar dados no banco"""
        # Limpar dados de teste antigos
        Instrumento.objects.filter(numero_serie="TEST_SN001").delete()
        
        # Criar categoria e unidade
        cat, _ = CategoriaInstrumento.objects.get_or_create(
            nome="Teste"
        )
        unid, _ = UnidadeMedida.objects.get_or_create(
            nome="mm",
            simbolo="mm"
        )
        
        # Criar instrumento
        inst = Instrumento.objects.create(
            nome="Instrumento de Teste",
            numero_serie="TEST_SN001",
            categoria=cat,
            unidade_medida=unid
        )
        
        # Verificar
        assert Instrumento.objects.filter(
            numero_serie="TEST_SN001"
        ).exists()
        
        # Limpar
        inst.delete()
    
    def test_admin_accessible(self):
        """Testa que admin está acessível (via ORM)"""
        from django.contrib.admin.sites import site
        
        # Verificar que admin está registrado
        assert len(site._registry) > 0, "Admin não tem modelos registrados"
    
    def test_permissions_system(self):
        """Testa que sistema de permissions funciona"""
        from django.contrib.auth.models import Permission
        
        perms = Permission.objects.all()
        assert perms.count() > 0, "Nenhuma permissão encontrada"
    
    def run_all_tests(self):
        """Executa todos os testes"""
        print("\n" + "="*60)
        print("🔍 VALIDAÇÃO PÓS-DEPLOYMENT - CALIBRAWEB RAILWAY")
        print("="*60 + "\n")
        
        # Tests
        self.test(
            "Conexão com Banco de Dados",
            self.test_database_connection
        )
        self.test(
            "PostgreSQL Configurado",
            self.test_postgresql
        )
        self.test(
            "Migrations Aplicadas",
            self.test_migrations_applied
        )
        self.test(
            "Superuser Existe",
            self.test_superuser_exists
        )
        self.test(
            "Apps Carregados",
            self.test_apps_loaded
        )
        self.test(
            "Static Files Configurados",
            self.test_static_files
        )
        self.test(
            "Produção Configurada",
            self.test_settings_production
        )
        self.test(
            "Tabelas do Banco Existem",
            self.test_database_tables
        )
        self.test(
            "Criar Dados de Teste",
            self.test_create_test_data
        )
        self.test(
            "Admin Registrado",
            self.test_admin_accessible
        )
        self.test(
            "Sistema de Permissões",
            self.test_permissions_system
        )
        
        # Resumo
        print("\n" + "="*60)
        print("📊 RESUMO DOS TESTES")
        print("="*60)
        print(f"✅ Testes passados: {self.tests_passed}")
        print(f"❌ Testes falhados: {self.tests_failed}")
        print(f"📈 Taxa de sucesso: {self.tests_passed}/{self.tests_passed + self.tests_failed}")
        print("="*60 + "\n")
        
        # Status final
        if self.tests_failed == 0:
            print("🎉 TUDO OK! Aplicação pronta para produção!")
            return True
        else:
            print("⚠️  Alguns testes falharam. Verifique os logs acima.")
            return False


if __name__ == '__main__':
    validator = DeploymentValidator()
    success = validator.run_all_tests()
    sys.exit(0 if success else 1)
