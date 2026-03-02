#!/usr/bin/env python
"""
Script para verificar os números de treinamentos do colaborador específico.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador
from procedures.models import ColaboradorPerfil, RegistroTreinamento
from datetime import date

# Colaborador específico (AFONSO PAULO RODRIGUES BEZERRA, id=4)
colab = Colaborador.objects.get(id=4)
print(f"Colaborador: {colab.nome_completo} (ID: {colab.id})")
print("=" * 70)

# Método 1: Contar todos os registros de treinamento (OLD)
treinamentos_old = colab.treinamentos.all()
print(f"\n1️⃣ MÉTODO ANTIGO (contar todos os registros):")
print(f"   Total: {treinamentos_old.count()}")

vig_old = 0
pend_old = 0
for rt in treinamentos_old:
    status = rt.status_treinamento
    if status in ("OK", "VIGENTE"):
        vig_old += 1
    else:
        pend_old += 1

print(f"   Vigentes: {vig_old}")
print(f"   Pendentes: {pend_old}")

# Método 2: Contar procedimentos únicos por perfil (NEW)
print(f"\n2️⃣ MÉTODO NOVO (contar procedimentos únicos por perfil):")

perfis_colab = ColaboradorPerfil.objects.filter(
    colaborador=colab, ativo=True
).select_related('perfil').prefetch_related(
    'perfil__grupos__subgrupos__procedimentos'
)

print(f"   Perfis ativos: {perfis_colab.count()}")

procedimentos_contabilizados = set()
vig_new = 0
pend_new = 0

for cp in perfis_colab:
    perfil = cp.perfil
    grupos_selecionados_ids = cp.grupos_selecionados.get('grupos', []) if cp.grupos_selecionados else []
    subgrupos_selecionados_ids = cp.grupos_selecionados.get('subgrupos', []) if cp.grupos_selecionados else []
    
    print(f"\n   Perfil: {perfil.codigo} ({perfil.nome})")
    perfil_total = 0
    perfil_pendentes = 0
    
    for grupo in perfil.grupos.all():
        if grupos_selecionados_ids and grupo.id not in grupos_selecionados_ids:
            continue
        
        for subgrupo in grupo.subgrupos.all():
            if subgrupos_selecionados_ids and subgrupo.id not in subgrupos_selecionados_ids:
                continue
            
            for proc in subgrupo.procedimentos.all():
                if proc.id not in procedimentos_contabilizados:
                    procedimentos_contabilizados.add(proc.id)
                    perfil_total += 1
                    
                    treinamento = colab.treinamentos.filter(procedimento=proc).first()
                    if treinamento:
                        status = treinamento.status_treinamento
                        if status in ("OK", "VIGENTE"):
                            vig_new += 1
                        else:
                            pend_new += 1
                            perfil_pendentes += 1
                    else:
                        pend_new += 1
                        perfil_pendentes += 1
    
    print(f"     - Total do perfil: {perfil_total}")
    print(f"     - Pendentes do perfil: {perfil_pendentes}")

print(f"\n   Total único: {len(procedimentos_contabilizados)}")
print(f"   Vigentes: {vig_new}")
print(f"   Pendentes: {pend_new}")

print(f"\n3️⃣ COMPARAÇÃO:")
print(f"   Diferença (Antigo - Novo): {treinamentos_old.count()} - {len(procedimentos_contabilizados)} = {treinamentos_old.count() - len(procedimentos_contabilizados)}")
print(f"   Vigentes (Antigo - Novo): {vig_old} - {vig_new} = {vig_old - vig_new}")
print(f"   Pendentes (Antigo - Novo): {pend_old} - {pend_new} = {pend_old - pend_new}")

