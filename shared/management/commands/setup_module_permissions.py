"""
Comando Django para configurar grupos de permissões por módulo.

Uso:
    python manage.py setup_module_permissions
"""

from django.core.management.base import BaseCommand
from shared.permissions import setup_module_groups


class Command(BaseCommand):
    help = 'Configura grupos de permissões para cada módulo da aplicação'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔐 Configurando permissões dos módulos...')
        )
        
        try:
            setup_module_groups()
            self.stdout.write(
                self.style.SUCCESS('✅ Permissões configuradas com sucesso!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro: {str(e)}')
            )
