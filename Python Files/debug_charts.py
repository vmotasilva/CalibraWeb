#!/usr/bin/env python
"""Script para debugar dados dos gráficos do dashboard"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador
from procedures.models import RegistroTreinamento
from core.models import TURNOS_CHOICES
from organization.models import Setor

print("\n=== TESTE COM NOVA LÓGICA ===\n")

# Gráfico por Líder
print("=== DADOS PARA GRÁFICO POR LÍDER ===")
treinamentos_por_lider = []
líderes = Colaborador.objects.filter(
    liderados__isnull=False, 
    liderados__is_active=True
).distinct().order_by('nome_completo')

print(f"Líderes com liderados ativos: {líderes.count()}")

for lider in líderes:
    # Pegar todos os liderados ativos deste líder
    liderados_ids = lider.liderados.filter(is_active=True).values_list('id', flat=True)
    
    # Contar registros de treinamento
    vigentes = RegistroTreinamento.objects.filter(
        colaborador_id__in=liderados_ids,
        data_treinamento__isnull=False
    ).count()
    pendentes = RegistroTreinamento.objects.filter(
        colaborador_id__in=liderados_ids,
        data_treinamento__isnull=True
    ).count()
    
    # Incluir se tem qualquer registro
    total = vigentes + pendentes
    if total > 0:
        print(f"  - {lider.nome_completo}: Vigentes={vigentes}, Pendentes={pendentes}")
        treinamentos_por_lider.append({
            'nome': lider.nome_completo[:25],
            'vigentes': vigentes,
            'pendentes': pendentes
        })

# Ordenar por total descendente e pegar top 10
treinamentos_por_lider.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
treinamentos_por_lider = treinamentos_por_lider[:10]

print(f"\nTotal com dados: {len(treinamentos_por_lider)}")

# Gráfico por Setor e Turno
print("\n=== DADOS PARA GRÁFICO POR SETOR E TURNO ===")
treinamentos_por_setor_turno = []

# Pegar combinações únicas de setor + turno
combinacoes = Colaborador.objects.filter(
    setor__isnull=False,
    is_active=True
).values_list('setor_id', 'turno').distinct()

print(f"Combinações de setor+turno: {combinacoes.count()}")

for setor_id, turno in combinacoes:
    try:
        setor = Setor.objects.get(id=setor_id)
        
        # Pegar todos os colaboradores ativos neste setor e turno
        colaboradores_ids = Colaborador.objects.filter(
            setor_id=setor_id,
            turno=turno,
            is_active=True
        ).values_list('id', flat=True)
        
        # Contar registros de treinamento
        vigentes = RegistroTreinamento.objects.filter(
            colaborador_id__in=colaboradores_ids,
            data_treinamento__isnull=False
        ).count()
        pendentes = RegistroTreinamento.objects.filter(
            colaborador_id__in=colaboradores_ids,
            data_treinamento__isnull=True
        ).count()
        
        # Incluir se tem qualquer registro
        total = vigentes + pendentes
        if total > 0:
            # Mapear turno para label legível usando TURNOS_CHOICES
            turno_dict = dict(TURNOS_CHOICES)
            turno_label = turno_dict.get(turno, turno)
            
            print(f"  - {setor.nome} - {turno_label}: Vigentes={vigentes}, Pendentes={pendentes}")
            treinamentos_por_setor_turno.append({
                'nome': f'{setor.nome} - {turno_label}'[:40],
                'vigentes': vigentes,
                'pendentes': pendentes
            })
    except Exception as e:
        print(f"  Erro ao processar setor {setor_id}: {e}")

# Ordenar por total descendente e pegar top 10
treinamentos_por_setor_turno.sort(key=lambda x: x['vigentes'] + x['pendentes'], reverse=True)
treinamentos_por_setor_turno = treinamentos_por_setor_turno[:10]

print(f"\nTotal com dados: {len(treinamentos_por_setor_turno)}")

print("\n✅ Debug completo!")

