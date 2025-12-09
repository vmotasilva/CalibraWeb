#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verify that all 27 models are registered in Django admin
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib import admin

# Import all models
from core.models import UnidadeMedida
from organization.models import Setor, CentroCusto, HierarquiaSetor
from rh.models import Colaborador, Ferias, Ocorrencia, DocumentoPessoal
from metrologia.models import CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao, ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao
from procurements.models import Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
from training.models import Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento
from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob

# List of all models
models_to_check = [
    UnidadeMedida, Setor, CentroCusto, HierarquiaSetor,
    Colaborador, Ferias, Ocorrencia, DocumentoPessoal,
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao, ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao,
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento,
    Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento,
    SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob
]

# Check registration
registered_count = 0
missing_models = []

for model in models_to_check:
    if model in admin.site._registry:
        registered_count += 1
    else:
        missing_models.append(model.__name__)

print(f"✅ {registered_count}/27 models registered in Django admin")
if missing_models:
    print(f"❌ Missing: {', '.join(missing_models)}")
else:
    print("✅ ALL 27 MODELS SUCCESSFULLY REGISTERED IN ADMIN")
