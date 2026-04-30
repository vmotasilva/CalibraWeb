#!/usr/bin/env python
"""
Script para visualizar associações de DisciplinaProcedimento
Ajuda a diagnosticar por que procedimentos não aparecem
"""

import os
import sys
import django

import os
import sys
import django

# Setup Django
sys.path.insert(0, 'c:\\CalibraWeb')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import Disciplina, DisciplinaProcedimento, Procedimento
from django.db.models import Count, Q

def show_disciplina_stats():
    """Mostra estatísticas sobre disciplinas e seus procedimentos"""
    
    print("\n" + "="*100)
    print("ANÁLISE: Associações de Disciplinas e Procedimentos")
    print("="*100)
    
    # Estatísticas gerais
    total_disciplinas = Disciplina.objects.count()
    total_procedimentos = Procedimento.objects.count()
    total_associacoes = DisciplinaProcedimento.objects.count()
    
    print(f"\n📊 ESTATÍSTICAS GERAIS:")
    print(f"   • Total de Disciplinas: {total_disciplinas}")
    print(f"   • Total de Procedimentos: {total_procedimentos}")
    print(f"   • Total de Associações DisciplinaProcedimento: {total_associacoes}")
    
    # Disciplinas com procedimentos
    disciplinas_com_proc = Disciplina.objects.annotate(
        proc_count=Count('procedimentos_associados')
    ).filter(proc_count__gt=0).order_by('-proc_count')
    
    print(f"\n✅ DISCIPLINAS COM PROCEDIMENTOS ASSOCIADOS ({disciplinas_com_proc.count()}):")
    for disciplina in disciplinas_com_proc[:10]:
        proc_count = disciplina.proc_count
        print(f"\n   [{disciplina.id}] {disciplina.codigo} - {disciplina.nome}")
        print(f"       └─ {proc_count} procedimento(s) associado(s)")
        
        # Mostrar alguns procedimentos
        for dp in DisciplinaProcedimento.objects.filter(disciplina=disciplina)[:3]:
            print(f"          • {dp.procedimento.codigo} - {dp.procedimento.nome}")
        
        if proc_count > 3:
            print(f"          ... e mais {proc_count - 3}")
    
    # Disciplinas SEM procedimentos
    disciplinas_sem_proc = Disciplina.objects.annotate(
        proc_count=Count('procedimentos_associados')
    ).filter(proc_count=0)
    
    if disciplinas_sem_proc.exists():
        print(f"\n❌ DISCIPLINAS SEM PROCEDIMENTOS ASSOCIADOS ({disciplinas_sem_proc.count()}):")
        for disciplina in disciplinas_sem_proc[:10]:
            print(f"\n   [{disciplina.id}] {disciplina.codigo} - {disciplina.nome}")
            
            # Tentar encontrar procedimentos por nome matching
            match_por_nome = Procedimento.objects.filter(
                Q(nome__icontains=disciplina.nome) |
                Q(codigo__icontains=disciplina.codigo)
            )
            
            if match_por_nome.exists():
                print(f"       └─ 🔍 Encontrados por name matching: {match_por_nome.count()}")
                for proc in match_por_nome[:2]:
                    print(f"          • {proc.codigo} - {proc.nome}")
            else:
                print(f"       └─ ⚠️ Nenhum procedimento encontrado")
        
        if disciplinas_sem_proc.count() > 10:
            print(f"\n   ... e mais {disciplinas_sem_proc.count() - 10} disciplinas sem associações")
    
    # Procedimentos não associados
    procedimentos_nao_assoc = Procedimento.objects.exclude(
        id__in=DisciplinaProcedimento.objects.values_list('procedimento', flat=True)
    )
    
    print(f"\n📋 PROCEDIMENTOS NÃO ASSOCIADOS A NENHUMA DISCIPLINA: {procedimentos_nao_assoc.count()}")
    
    # Recomendações
    print("\n" + "="*100)
    print("💡 RECOMENDAÇÕES:")
    print("="*100)
    
    if total_associacoes == 0:
        print("""
   ⚠️  NÃO HÁ NENHUMA ASSOCIAÇÃO CRIADA!
   
   Para que procedimentos apareçam automaticamente, você precisa:
   
   1. Abrir Django Admin: http://localhost:8000/admin/
   2. Ir em: Procedures > Disciplina Procedimento
   3. Clicar em "Add Disciplina Procedimento"
   4. Selecionar Disciplina e Procedimento
   5. Salvar
   
   OU
   
   Use a estratégia de fallback da API que procura por:
   - Nome do procedimento similar à disciplina
   - Código do procedimento similar à disciplina
   - Procedimentos da mesma matriz
        """)
    elif disciplinas_sem_proc.count() > 0:
        print(f"""
   ⚠️  {disciplinas_sem_proc.count()} disciplinas sem procedimentos associados!
   
   Para essas disciplinas, a API tentará:
   1. Buscar por similaridade de nome (mais recomendado)
   2. Buscar por procedimentos da mesma matriz
   3. Retornar qualquer procedimento disponível
   
   Para melhorar, crie associações explícitas no Django Admin.
        """)
    else:
        print("""
   ✅ Todas as disciplinas têm procedimentos associados!
   
   A API retornará procedimentos diretos sem precisar de fallback.
        """)
    
    print("="*100 + "\n")

if __name__ == '__main__':
    show_disciplina_stats()
