#!/usr/bin/env python
"""Script para verificar se os IDs dos filtros estão corretos na view RH"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rh.models import Colaborador
from organization.models import Setor
from django.db.models import Q, Prefetch
from datetime import date

print("=" * 80)
print("SIMULANDO LÓGICA DA VIEW modulo_rh_view")
print("=" * 80)

# Simular o que a view faz
ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))

# Pré-carregar férias ativas usando Prefetch
from rh.models import Ferias
prefetch_ferias = Prefetch(
    'ferias_set',
    queryset=Ferias.objects.filter(
        aprovada=True,
        data_inicio__lte=date.today(),
        data_fim__gte=date.today()
    ).order_by('-data_inicio')
)

# QuerySet base
funcionarios_base = Colaborador.objects.filter(
    id__in=list(ids_permitidos)
).select_related(
    'setor', 'centro_custo', 'lider', 'supervisor', 'gerente'
).prefetch_related(
    'treinamentos__procedimento',
    prefetch_ferias
).order_by("nome_completo")

print(f"\nTotal de funcionários carregados: {funcionarios_base.count()}")

# Extrair opções de filtro
setores_ids = set()
lideres_ids = set()
supervisores_ids = set()
gerentes_ids = set()

for f in funcionarios_base:
    if f.setor_id:
        setores_ids.add(f.setor_id)
    if f.lider_id:
        lideres_ids.add(f.lider_id)
    if f.supervisor_id:
        supervisores_ids.add(f.supervisor_id)
    if f.gerente_id:
        gerentes_ids.add(f.gerente_id)

print(f"\nIDs únicos de LÍDERES extraídos: {len(lideres_ids)}")
print(f"IDs únicos de SUPERVISORES extraídos: {len(supervisores_ids)}")
print(f"IDs únicos de GERENTES extraídos: {len(gerentes_ids)}")

# Fazer queries bulk
lideres_filtro = Colaborador.objects.filter(id__in=lideres_ids).order_by("nome_completo") if lideres_ids else []
supervisores_filtro = Colaborador.objects.filter(id__in=supervisores_ids).order_by("nome_completo") if supervisores_ids else []
gerentes_filtro = Colaborador.objects.filter(id__in=gerentes_ids).order_by("nome_completo") if gerentes_ids else []

print(f"\nLIDERES para filtro: {lideres_filtro.count()}")
for lider in lideres_filtro[:5]:
    print(f"  ID={lider.id}, Nome={lider.nome_completo}")

print(f"\nSUPERVISORES para filtro: {supervisores_filtro.count()}")
for sup in supervisores_filtro[:5]:
    print(f"  ID={sup.id}, Nome={sup.nome_completo}")

print(f"\nGERENTES para filtro: {gerentes_filtro.count()}")
for ger in gerentes_filtro[:5]:
    print(f"  ID={ger.id}, Nome={ger.nome_completo}")

# Verificar se o relacionamento está correto (quando um lider aparece na lista, seu ID deveria ser seu ID real)
print("\n" + "=" * 80)
print("VERIFICANDO CONSISTÊNCIA DE IDs")
print("=" * 80)

# Pegar um colaborador que tem um lider
colab_com_lider = funcionarios_base.filter(lider__isnull=False).first()
if colab_com_lider:
    print(f"\nColaborador: {colab_com_lider.nome_completo} (ID={colab_com_lider.id})")
    print(f"  Seu líder (via relacionamento): ID={colab_com_lider.lider.id}, Nome={colab_com_lider.lider.nome_completo}")
    
    # Verificar se este ID está nos lideres_filtro
    lider_direto = colab_com_lider.lider
    
    em_filtro = any(l.id == lider_direto.id for l in lideres_filtro)
    print(f"  Este líder está em lideres_filtro? {em_filtro}")
    
    # A URL que seria gerada seria:
    print(f"  URL que seria gerada: /rh/colaborador/{lider_direto.id}/")

# Agora verificar especificamente o ID 159
print("\n" + "=" * 80)
print("VERIFICANDO ID 159 (ROMULO BARBOSA)")
print("=" * 80)

try:
    romulo = Colaborador.objects.get(id=159)
    print(f"\nID: 159")
    print(f"Nome: {romulo.nome_completo}")
    print(f"Matrícula: {romulo.matricula}")
    print(f"URL correta: /rh/colaborador/159/")
    
    # Verificar quantas vezes este ID aparece em relacionamentos
    liderados_por_159 = Colaborador.objects.filter(lider_id=159).count()
    supervisionados_por_159 = Colaborador.objects.filter(supervisor_id=159).count()
    gerenciados_por_159 = Colaborador.objects.filter(gerente_id=159).count()
    
    print(f"\nColaboradores que têm 159 como LIDER: {liderados_por_159}")
    print(f"Colaboradores que têm 159 como SUPERVISOR: {supervisionados_por_159}")
    print(f"Colaboradores que têm 159 como GERENTE: {gerenciados_por_159}")
    
except Colaborador.DoesNotExist:
    print("ID 159 não encontrado!")

print("\n" + "=" * 80)
print("FIM DO DEBUG")
print("=" * 80)
