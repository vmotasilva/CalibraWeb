#!/usr/bin/env python
"""
Script para testar a correção de duplicação de procedimentos
na tela de detalhe do colaborador.

Verifica se procedimentos que aparecem em múltiplos perfis
estão sendo contabilizados apenas uma vez.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, r'c:\Users\Vinícius Mota\Documents\PYTHON\CalibraWeb')

django.setup()

from rh.models import Colaborador
from procedures.models import (
    PerfilTreinamento, 
    GrupoTreinamento, 
    SubGrupoTreinamento,
    Procedimento,
    ColaboradorPerfil
)
from django.db.models import Q

def testar_duplicacao():
    """Testa se há duplicações de procedimentos em múltiplos perfis"""
    
    print("=" * 80)
    print("🔍 TESTE DE DUPLICAÇÃO DE PROCEDIMENTOS")
    print("=" * 80)
    
    # Buscar colaboradores com múltiplos perfis
    colaboradores_multiplos_perfis = Colaborador.objects.filter(
        perfis_treinamento__ativo=True
    ).annotate(
        perfis_count=django.db.models.Count('perfis_treinamento', distinct=True)
    ).filter(perfis_count__gt=1).distinct()
    
    if not colaboradores_multiplos_perfis.exists():
        print("⚠️  Nenhum colaborador com múltiplos perfis encontrado.")
        return
    
    print(f"\n📊 Encontrados {colaboradores_multiplos_perfis.count()} colaboradores com múltiplos perfis:\n")
    
    for colab in colaboradores_multiplos_perfis:
        print(f"\n{'─' * 80}")
        print(f"👤 Colaborador: {colab.nome_completo} (ID: {colab.id})")
        print(f"{'─' * 80}")
        
        # Buscar todos os perfis deste colaborador
        perfis_cp = ColaboradorPerfil.objects.filter(
            colaborador=colab,
            ativo=True
        ).select_related('perfil').prefetch_related(
            'perfil__grupos__subgrupos__procedimentos'
        )
        
        print(f"📋 Perfis Associados: {perfis_cp.count()}")
        
        todos_procedimentos = []
        procedimentos_por_perfil = {}
        
        for cp in perfis_cp:
            perfil = cp.perfil
            print(f"\n  ✓ {perfil.codigo} - {perfil.nome}")
            
            procedimentos_perfil = set()
            
            for grupo in perfil.grupos.all():
                for subgrupo in grupo.subgrupos.all():
                    for proc in subgrupo.procedimentos.all():
                        procedimentos_perfil.add(proc.id)
                        todos_procedimentos.append({
                            'proc_id': proc.id,
                            'perfil_codigo': perfil.codigo,
                            'grupo': grupo.nome,
                            'subgrupo': subgrupo.nome,
                            'procedimento': proc.codigo
                        })
            
            procedimentos_por_perfil[perfil.codigo] = procedimentos_perfil
            print(f"    Procedimentos: {len(procedimentos_perfil)}")
        
        # Detectar duplicatas
        print(f"\n  📈 Análise de Duplicações:")
        
        # Total sem deduplicação (problema original)
        total_sem_dedup = len(todos_procedimentos)
        print(f"    - Total sem deduplicação: {total_sem_dedup}")
        
        # Total com deduplicação (solução correta)
        total_com_dedup = len(set(p['proc_id'] for p in todos_procedimentos))
        print(f"    - Total com deduplicação: {total_com_dedup}")
        
        # Encontrar procedimentos duplicados
        procs_contados = {}
        for item in todos_procedimentos:
            proc_id = item['proc_id']
            if proc_id not in procs_contados:
                procs_contados[proc_id] = []
            procs_contados[proc_id].append(item)
        
        duplicados = {k: v for k, v in procs_contados.items() if len(v) > 1}
        
        if duplicados:
            print(f"\n  ⚠️  DUPLICATAS ENCONTRADAS ({len(duplicados)}):")
            for proc_id, items in duplicados.items():
                print(f"\n    Procedimento ID {proc_id}:")
                for item in items:
                    print(f"      - {item['procedimento']} em {item['perfil_codigo']} > {item['grupo']} > {item['subgrupo']}")
                print(f"      ❌ CONTADO {len(items)} VEZES (deveria ser 1)")
        else:
            print(f"\n  ✅ Nenhuma duplicação detectada!")
        
        # Diferença
        diferenca = total_sem_dedup - total_com_dedup
        if diferenca > 0:
            print(f"\n  ⚠️  DIFERENÇA: {diferenca} procedimento(s) contado(s) a mais!")
        else:
            print(f"\n  ✅ Contagem correta!")
    
    print(f"\n{'=' * 80}")
    print("✅ TESTE CONCLUÍDO")
    print(f"{'=' * 80}\n")

if __name__ == '__main__':
    testar_duplicacao()
