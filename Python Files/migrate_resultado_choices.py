#!/usr/bin/env python
"""
Script to migrate ResultadoFaixaCalibracao result values from old choices to new ones.
Old choices: OK, FORA
New choices: APROVADO_SEM_CORRECAO, APROVADO_COM_CORRECAO, REPROVADO
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from metrologia.models import ResultadoFaixaCalibracao

# Mapping from old values to new values
MIGRATION_MAP = {
    'OK': 'APROVADO_SEM_CORRECAO',
    'FORA': 'REPROVADO',
}

def migrate_resultado_choices():
    """Migrate old resultado choices to new ones."""
    print("Starting migration of ResultadoFaixaCalibracao.resultado field...")
    
    total = ResultadoFaixaCalibracao.objects.count()
    print(f"Total ResultadoFaixaCalibracao records: {total}")
    
    if total == 0:
        print("No records to migrate.")
        return
    
    # Check for old values
    for old_value, new_value in MIGRATION_MAP.items():
        count = ResultadoFaixaCalibracao.objects.filter(resultado=old_value).count()
        if count > 0:
            print(f"\nMigrating {count} records from '{old_value}' to '{new_value}'...")
            ResultadoFaixaCalibracao.objects.filter(resultado=old_value).update(resultado=new_value)
            print(f"✓ Successfully migrated {count} records")
    
    # Show final distribution
    print("\nFinal distribution of resultado values:")
    for choice, _ in ResultadoFaixaCalibracao.RESULTADO_CHOICES:
        count = ResultadoFaixaCalibracao.objects.filter(resultado=choice).count()
        print(f"  {choice}: {count} records")
    
    print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    migrate_resultado_choices()
