#!/usr/bin/env python
"""
Script de teste para a API de procedimentos por disciplina
Verifica se a API está retornando procedimentos corretamente
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibraweb.settings')
django.setup()

from procedures.models import Disciplina, DisciplinaProcedimento, Procedimento

def test_discipline_procedures():
    """Testa se há procedimentos associados às disciplinas"""
    
    print("\n" + "="*80)
    print("TESTE: Procedimentos por Disciplina")
    print("="*80)
    
    # Contar disciplinas
    disciplinas = Disciplina.objects.all()
    print(f"\nTotal de Disciplinas: {disciplinas.count()}")
    
    for disciplina in disciplinas[:5]:  # Mostrar primeiras 5
        print(f"\n--- Disciplina: {disciplina.id} | {disciplina.codigo} - {disciplina.nome} ---")
        print(f"    Matriz: {disciplina.matriz}")
        
        # Verificar DisciplinaProcedimento
        dp_count = DisciplinaProcedimento.objects.filter(disciplina=disciplina).count()
        print(f"    DisciplinaProcedimento: {dp_count}")
        
        if dp_count > 0:
            for dp in DisciplinaProcedimento.objects.filter(disciplina=disciplina)[:3]:
                print(f"      ✓ {dp.procedimento.codigo} - {dp.procedimento.nome}")
        
        # Verificar procedimentos por name matching
        proc_name_match = Procedimento.objects.filter(
            nome__icontains=disciplina.nome.split('-')[0].strip()
        ).count()
        print(f"    Procedimentos por name matching: {proc_name_match}")
        
        # Total de procedimentos no sistema
        total_proc = Procedimento.objects.count()
        print(f"    Total procedimentos no sistema: {total_proc}")
    
    print("\n" + "="*80)
    print("Resumo: Verifique se DisciplinaProcedimento tem associações")
    print("Se faltarem, crie-as via Django Admin em procedures > Disciplina Procedimento")
    print("="*80 + "\n")

if __name__ == '__main__':
    test_discipline_procedures()
