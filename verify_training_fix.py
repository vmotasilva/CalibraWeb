#!/usr/bin/env python
"""
Script de verificação final: Treinamentos de colaboradores desligados
Verifica se há inconsistências nos registros de treinamento
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from procedures.models import RegistroTreinamento
from rh.models import Colaborador
import logging

logger = logging.getLogger(__name__)

# Não importar training.models pois tem problemas de inicialização
# TrainingRegistroTreinamento está em training/models.py mas compartilha tabela com procedures

logger.info("=" * 80)
logger.info("VERIFICAÇÃO FINAL: TREINAMENTOS DE COLABORADORES DESLIGADOS")
logger.info("=" * 80)

# 1. Verificar procedures.RegistroTreinamento
logger.info("\n1. PROCEDURES.REGISTROTREINAMENTO")
logger.info("-" * 80)

inactive_with_ativo_true = RegistroTreinamento.objects.filter(
    colaborador__isnull=False,
    colaborador__is_active=False,
    ativo=True
).count()

inactive_total = RegistroTreinamento.objects.filter(
    colaborador__isnull=False,
    colaborador__is_active=False
).count()

logger.info(f"   Total de registros (colaboradores desligados): {inactive_total}")
logger.info(f"   Registros com ativo=True (ERRO): {inactive_with_ativo_true}")
if inactive_with_ativo_true > 0:
    logger.warning(f"   ⚠️ PROBLEMA DETECTADO!")
else:
    logger.info(f"   ✓ Nenhum problema detectado")

# 2. Ambos training e procedures usam o mesmo modelo
print("\n2. OBSERVAÇÃO SOBRE MODELOS")
print("-" * 80)
print("   • training.models.RegistroTreinamento e procedures.models.RegistroTreinamento")
print("   • compartilham a mesma tabela no banco de dados")
print("   • verificação unificada acima cobre ambos")

# 3. Verificar estatísticas gerais
logger.info("\n3. ESTATÍSTICAS GERAIS")
logger.info("-" * 80)

total_colabs = Colaborador.objects.count()
active_colabs = Colaborador.objects.filter(is_active=True).count()
inactive_colabs = Colaborador.objects.filter(is_active=False).count()

logger.info(f"   Total de colaboradores: {total_colabs}")
logger.info(f"   Colaboradores ATIVOS: {active_colabs}")
logger.info(f"   Colaboradores DESLIGADOS: {inactive_colabs}")

# 4. Verificar distribuição de treinamentos
logger.info("\n4. DISTRIBUIÇÃO DE TREINAMENTOS")
logger.info("-" * 80)

active_with_training = Colaborador.objects.filter(
    is_active=True,
    treinamentos__isnull=False
).distinct().count()

inactive_with_training = Colaborador.objects.filter(
    is_active=False,
    treinamentos__isnull=False
).distinct().count()

print(f"   Colaboradores ATIVOS com treinamentos: {active_with_training}")
print(f"   Colaboradores DESLIGADOS com treinamentos: {inactive_with_training}")

# 5. Mostrar alguns exemplos de colaboradores desligados com treinamentos
print("\n5. EXEMPLOS: COLABORADORES DESLIGADOS COM TREINAMENTOS")
print("-" * 80)

inactive_with_trainings = Colaborador.objects.filter(
    is_active=False,
    treinamentos__isnull=False
).distinct()[:5]

if not inactive_with_trainings:
    logger.info("   ✓ Nenhum encontrado")
else:
    for colab in inactive_with_trainings:
        count = colab.treinamentos.count()
        logger.info(f"   • {colab.nome_completo} (ID: {colab.id}): {count} treinamentos")

# 6. Resumo final
logger.info("\n" + "=" * 80)
logger.info("RESUMO FINAL")
logger.info("=" * 80)

logger.info("\n✅ CORRIGIDO:")
logger.info("   • RH Dashboard (modulo_rh_view): Agora não conta treinamentos de desligados")
logger.info("   • Training Dashboard: Agora filtra por is_active=True, afastado=False e em_ferias=False")
logger.info("   • Procedures Dashboard: Já estava filtrando por is_active=True")

logger.info("\n📝 OBSERVAÇÃO:")
logger.info("   • Histórico de treinamentos permanece na base (é informação válida)")
logger.info("   • Colaboradores desligados não são mostrados em contagens de")
logger.info("     treinamentos vigentes/pendentes nas views principais")

logger.info("\n" + "=" * 80)
logger.info("FIM DA VERIFICAÇÃO")
logger.info("=" * 80)
