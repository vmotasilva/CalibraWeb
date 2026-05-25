import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.apps import apps
from io import StringIO

class Command(BaseCommand):
    help = "Resets all PostgreSQL primary key auto-increment sequences."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando o reset de sequencias de ID no PostgreSQL...")
        
        app_labels = [app.label for app in apps.get_app_configs()]
        
        sql_statements = []
        for app_label in app_labels:
            output = StringIO()
            try:
                call_command('sqlsequencereset', app_label, stdout=output)
                sql = output.getvalue().strip()
                if sql:
                    sql_statements.append(sql)
            except Exception:
                pass
        
        if sql_statements:
            self.stdout.write("Executando queries de reset no PostgreSQL...")
            statements = []
            for app_sql in sql_statements:
                for stmt in app_sql.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        statements.append(stmt)
            
            success_count = 0
            with connection.cursor() as cursor:
                for i, stmt in enumerate(statements, 1):
                    try:
                        cursor.execute(stmt)
                        success_count += 1
                    except Exception as e:
                        self.stderr.write(f"Erro no statement {i} ({stmt[:60]}...): {e}")
            
            self.stdout.write(self.style.SUCCESS(f"SUCESSO: {success_count}/{len(statements)} sequencias de ID foram sincronizadas com o banco!"))
        else:
            self.stdout.write("Nenhuma sequencia encontrada para resetar.")
