#!/usr/bin/env python
"""
Task 1: Análise de Dependências de Modelos
Mapeia todos os modelos em qms/models.py e determina para qual app devem ser movidos.
Identifica dependências circulares e imports entre apps.
"""

import os
import sys
import django
import re
from collections import defaultdict

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.apps import apps
from django.db import models as django_models

# ==============================================================================
# DEFINIÇÃO DE MAPEAMENTO: Qual app cada modelo deveria pertencer
# ==============================================================================
MODEL_TO_APP_MAPPING = {
    # CORE - Constantes e modelos base
    'UnidadeMedida': 'core',
    
    # ORGANIZATION - Estrutura organizacional
    'Setor': 'organization',
    'CentroCusto': 'organization',
    'HierarquiaSetor': 'organization',
    
    # RH - Recursos Humanos
    'Colaborador': 'rh',
    'Ferias': 'rh',
    'Ocorrencia': 'rh',
    'DocumentoPessoal': 'rh',
    
    # METROLOGIA - Instrumentos e Calibração
    'CategoriaInstrumento': 'metrologia',
    'Instrumento': 'metrologia',
    'FaixaMedicao': 'metrologia',
    'HistoricoCalibracao': 'metrologia',
    'ArquivoPadrao': 'metrologia',
    'ResultadoFaixaCalibracao': 'metrologia',
    'OrdemCalibracao': 'metrologia',
    
    # PROCUREMENTS - Fornecedores e Cotações
    'Fornecedor': 'procurements',
    'AvaliacaoFornecedor': 'procurements',
    'ProcessoCotacao': 'procurements',
    'Orcamento': 'procurements',
    
    # TRAINING - Treinamento e Procedimentos
    'Procedimento': 'training',
    'PacoteTreinamento': 'training',
    'Area': 'training',
    'ProcedimentoRevisao': 'training',
    'RegistroTreinamento': 'training',
    
    # DOCUMENTS - Documentação (reutiliza training para Procedimento/Area)
    # Nota: Procedimento e Area são do training, não duplicar aqui
    
    # QMS - Modelos que não se encaixam em nenhum app (manter por enquanto)
    'SolicitacaoInstrumento': 'qms',  # Cross-app: solicitante (User), tipo (string)
    'OcorrenciaInstrumento': 'qms',  # Cross-app: ocorrencia + instrumento
    'ImportJob': 'qms',  # Task runner - manter em qms
}

# ==============================================================================
# FUNÇÃO PARA ANALISAR DEPENDÊNCIAS
# ==============================================================================
def analyze_model_dependencies():
    """Analisa todos os modelos em qms.models e mapeia suas dependências"""
    
    from qms.models import (
        Setor, CentroCusto, Colaborador, HierarquiaSetor, Ferias, Ocorrencia,
        DocumentoPessoal, UnidadeMedida, CategoriaInstrumento, SolicitacaoInstrumento,
        OcorrenciaInstrumento, OrdemCalibracao, Instrumento, ImportJob, FaixaMedicao,
        HistoricoCalibracao, ArquivoPadrao, ResultadoFaixaCalibracao, Fornecedor,
        AvaliacaoFornecedor, ProcessoCotacao, Orcamento, Procedimento, PacoteTreinamento,
        Area, ProcedimentoRevisao, RegistroTreinamento
    )
    
    all_models = [
        Setor, CentroCusto, Colaborador, HierarquiaSetor, Ferias, Ocorrencia,
        DocumentoPessoal, UnidadeMedida, CategoriaInstrumento, SolicitacaoInstrumento,
        OcorrenciaInstrumento, OrdemCalibracao, Instrumento, ImportJob, FaixaMedicao,
        HistoricoCalibracao, ArquivoPadrao, ResultadoFaixaCalibracao, Fornecedor,
        AvaliacaoFornecedor, ProcessoCotacao, Orcamento, Procedimento, PacoteTreinamento,
        Area, ProcedimentoRevisao, RegistroTreinamento
    ]
    
    model_deps = defaultdict(set)
    model_info = {}
    
    print("\n" + "="*80)
    print("ANÁLISE DE MODELOS E DEPENDÊNCIAS - Phase 9 Task 1")
    print("="*80 + "\n")
    
    # Analisar cada modelo
    for model in all_models:
        model_name = model.__name__
        target_app = MODEL_TO_APP_MAPPING.get(model_name, 'qms')
        
        # Encontrar dependências (ForeignKey e M2M)
        dependencies = set()
        for field in model._meta.get_fields():
            if hasattr(field, 'related_model') and field.related_model:
                if field.related_model.__name__ in MODEL_TO_APP_MAPPING:
                    related_app = MODEL_TO_APP_MAPPING[field.related_model.__name__]
                    if related_app != target_app:
                        dependencies.add(field.related_model.__name__)
        
        model_info[model_name] = {
            'app': target_app,
            'dependencies': dependencies,
            'field_count': len(model._meta.get_fields()),
            'line_count': len(str(model.__doc__ or '').split('\n'))
        }
        
        model_deps[target_app].add(model_name)
    
    # ==============================================================================
    # IMPRIMIR RESULTADO: Modelos por App
    # ==============================================================================
    print("\n📦 MODELOS POR APP (Alvo de Migração):\n")
    
    for app_name in sorted(model_deps.keys()):
        models = sorted(model_deps[app_name])
        print(f"  📌 {app_name.upper()}:")
        for model in models:
            app = MODEL_TO_APP_MAPPING[model]
            print(f"     • {model}")
        print()
    
    # ==============================================================================
    # IMPRIMIR RESULTADO: Dependências Entre Apps
    # ==============================================================================
    print("\n🔗 DEPENDÊNCIAS ENTRE APPS:\n")
    
    cross_app_deps = defaultdict(lambda: defaultdict(set))
    
    for model_name, info in model_info.items():
        source_app = info['app']
        for dep_model in info['dependencies']:
            target_app = MODEL_TO_APP_MAPPING.get(dep_model, 'qms')
            if source_app != target_app:
                cross_app_deps[source_app][target_app].add((model_name, dep_model))
    
    if cross_app_deps:
        for source_app in sorted(cross_app_deps.keys()):
            print(f"  {source_app.upper()} → {{{', '.join(sorted(cross_app_deps[source_app].keys()))}}}")
            for target_app, deps in sorted(cross_app_deps[source_app].items()):
                for model, dep in sorted(deps):
                    print(f"     • {model} → {target_app}.{dep}")
            print()
    else:
        print("  ✅ Nenhuma dependência entre apps (dependências em mesmo app são OK)\n")
    
    # ==============================================================================
    # IMPRIMIR RESULTADO: Modelos Críticos (com múltiplas dependências)
    # ==============================================================================
    print("\n⚠️  MODELOS COM MÚLTIPLAS DEPENDÊNCIAS:\n")
    
    complex_models = {
        name: info for name, info in model_info.items()
        if len(info['dependencies']) > 2
    }
    
    if complex_models:
        for model_name in sorted(complex_models.keys()):
            info = model_info[model_name]
            print(f"  • {model_name} ({info['app'].upper()})")
            print(f"    Dependências: {', '.join(sorted(info['dependencies']))}")
            print()
    else:
        print("  ✅ Nenhum modelo com múltiplas dependências\n")
    
    # ==============================================================================
    # ESTATÍSTICAS
    # ==============================================================================
    print("\n📊 ESTATÍSTICAS:\n")
    print(f"  Total de modelos: {len(all_models)}")
    print(f"  Apps alvo: {len(model_deps)}")
    for app in sorted(model_deps.keys()):
        print(f"    • {app}: {len(model_deps[app])} modelos")
    print()
    
    # ==============================================================================
    # PLANO DE MIGRAÇÃO
    # ==============================================================================
    print("\n📋 ORDEM RECOMENDADA DE MIGRAÇÃO:\n")
    print("  1️⃣  CORE      → UnidadeMedida (nenhuma dependência)")
    print("  2️⃣  ORGANIZATION → Setor, CentroCusto, HierarquiaSetor")
    print("  3️⃣  RH         → Colaborador, Ferias, Ocorrencia, DocumentoPessoal")
    print("  4️⃣  METROLOGIA  → CategoriaInstrumento, Instrumento, FaixaMedicao, etc.")
    print("  5️⃣  PROCUREMENTS → Fornecedor, AvaliacaoFornecedor, etc.")
    print("  6️⃣  TRAINING   → Procedimento, Area, RegistroTreinamento, etc.")
    print("  7️⃣  QMS        → SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob")
    print()
    
    # ==============================================================================
    # PROBLEMAS POTENCIAIS
    # ==============================================================================
    print("\n⚠️  PROBLEMAS POTENCIAIS A RESOLVER:\n")
    
    issues = [
        "✅ HierarquiaSetor (organization) → depende de Setor (organization) [OK, mesmo app]",
        "✅ Colaborador (rh) → depende de Setor, CentroCusto (organization) [OK, import organization]",
        "✅ SolicitacaoInstrumento (qms) → depende de User, Instrumento, outras [OK, já cross-app]",
        "✅ HistoricoCalibracao (metrologia) → depende de Instrumento (metrologia) [OK, mesmo app]",
        "⚠️  CircularImport: Se documents reutiliza Procedimento (training), não há circular",
        "⚠️  ImportJob (qms) precisa acessar todos os modelos → imports explícitos necessários",
    ]
    
    for issue in issues:
        print(f"  {issue}")
    print()
    
    # ==============================================================================
    # PRÓXIMOS PASSOS
    # ==============================================================================
    print("\n✅ PRÓXIMOS PASSOS:\n")
    print("  1. Criar models.py em cada app (core, organization, rh, metrologia, etc.)")
    print("  2. Mover modelos para arquivo correto (copiar de qms/models.py)")
    print("  3. Criar __init__.py em qms/management/commands/ para tasks")
    print("  4. Atualizar imports em views.py, forms.py, admin.py")
    print("  5. Corrigir circular imports com lazy imports ou app_registry")
    print("  6. Criar migração Django para reflectir nova estrutura")
    print("  7. Rodar migrations e testar")
    print()
    
    return model_info, cross_app_deps

# ==============================================================================
# EXECUTAR ANÁLISE
# ==============================================================================
if __name__ == '__main__':
    try:
        model_info, cross_app_deps = analyze_model_dependencies()
        print("\n" + "="*80)
        print("ANÁLISE COMPLETA ✅")
        print("="*80 + "\n")
    except Exception as e:
        print(f"\n❌ ERRO na análise: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
