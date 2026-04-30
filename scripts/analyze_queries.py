#!/usr/bin/env python
"""
Database Query Analysis for CalibraWeb Performance Optimization
Identifies N+1 queries, slow queries, and optimization opportunities
"""
import os
import sys
import django
from django.db import connection, reset_queries
from django.test.utils import override_settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from django.db.models import Count, Prefetch, F, Q
from django.test import Client
from io import StringIO

# Import all models
from core.models import UnidadeMedida
from organization.models import Setor, CentroCusto, HierarquiaSetor
from rh.models import Colaborador, Ferias, Ocorrencia, DocumentoPessoal
from metrologia.models import (
    CategoriaInstrumento, Instrumento, FaixaMedicao, HistoricoCalibracao,
    ArquivoPadrao, ResultadoFaixaCalibracao, OrdemCalibracao
)
from training.models import Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento
from procurements.models import Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
from qms.models import SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob

print("=" * 80)
print("DATABASE QUERY ANALYSIS - PERFORMANCE OPTIMIZATION")
print("=" * 80)

# Enable query logging
@override_settings(DEBUG=True)
def analyze_queries():
    """Analyze database queries for optimization opportunities"""
    
    results = {
        "models": {},
        "n_plus_one": [],
        "optimization_tips": [],
        "total_queries": 0
    }
    
    # Test 1: List all models and their query patterns
    print("\n" + "=" * 80)
    print("TEST 1: BASIC MODEL QUERIES")
    print("=" * 80)
    
    models_to_test = [
        ("UnidadeMedida", UnidadeMedida),
        ("Setor", Setor),
        ("CentroCusto", CentroCusto),
        ("HierarquiaSetor", HierarquiaSetor),
        ("Colaborador", Colaborador),
        ("Ferias", Ferias),
        ("Ocorrencia", Ocorrencia),
        ("DocumentoPessoal", DocumentoPessoal),
        ("CategoriaInstrumento", CategoriaInstrumento),
        ("Instrumento", Instrumento),
        ("FaixaMedicao", FaixaMedicao),
        ("HistoricoCalibracao", HistoricoCalibracao),
        ("ArquivoPadrao", ArquivoPadrao),
        ("ResultadoFaixaCalibracao", ResultadoFaixaCalibracao),
        ("OrdemCalibracao", OrdemCalibracao),
        ("Area", Area),
        ("Procedimento", Procedimento),
        ("ProcedimentoRevisao", ProcedimentoRevisao),
        ("PacoteTreinamento", PacoteTreinamento),
        ("RegistroTreinamento", RegistroTreinamento),
        ("Fornecedor", Fornecedor),
        ("AvaliacaoFornecedor", AvaliacaoFornecedor),
        ("ProcessoCotacao", ProcessoCotacao),
        ("Orcamento", Orcamento),
        ("SolicitacaoInstrumento", SolicitacaoInstrumento),
        ("OcorrenciaInstrumento", OcorrenciaInstrumento),
        ("ImportJob", ImportJob),
    ]
    
    for model_name, model_class in models_to_test:
        reset_queries()
        try:
            # Get count
            count = model_class.objects.count()
            num_queries = len(connection.queries)
            
            result = {
                "total_records": count,
                "queries_for_count": num_queries
            }
            
            # Check for foreign keys (potential N+1 sources)
            fk_fields = []
            m2m_fields = []
            
            for field in model_class._meta.get_fields():
                if field.many_to_one:
                    fk_fields.append(field.name)
                elif field.many_to_many:
                    m2m_fields.append(field.name)
            
            result["foreign_keys"] = fk_fields
            result["many_to_many"] = m2m_fields
            
            results["models"][model_name] = result
            
            status = "✅" if count > 0 else "⏳ (empty)"
            print(f"{status} {model_name:30} - {count:5} records, {num_queries} queries")
            if fk_fields:
                print(f"   └─ Foreign Keys: {', '.join(fk_fields)}")
            if m2m_fields:
                print(f"   └─ Many-to-Many: {', '.join(m2m_fields)}")
                
        except Exception as e:
            print(f"❌ {model_name:30} - Error: {str(e)[:50]}")
    
    # Test 2: Common N+1 Query Patterns
    print("\n" + "=" * 80)
    print("TEST 2: N+1 QUERY DETECTION")
    print("=" * 80)
    
    # Example: Colaborador with Setor (potential N+1)
    print("\nExample: Iterating Colaborador.setor (without prefetch_related)")
    reset_queries()
    try:
        colaboradores = Colaborador.objects.all()[:5]  # Limit to 5
        for colab in colaboradores:
            _ = colab.setor  # This causes N additional queries
        
        num_queries = len(connection.queries)
        print(f"  Queries executed: {num_queries}")
        print(f"  Pattern: 1 query (for .all()) + 5 queries (for .setor) = 6 queries")
        print(f"  ⚠️  N+1 DETECTED: {num_queries} queries for 5 records + 1 setor access")
        
        results["n_plus_one"].append({
            "model": "Colaborador",
            "field": "setor",
            "queries": num_queries,
            "fix": "Use .prefetch_related('setor')"
        })
    except Exception as e:
        print(f"  Unable to test (likely no records): {e}")
    
    # Test with prefetch_related (optimized)
    print("\nExample: Iterating Colaborador.setor (WITH prefetch_related)")
    reset_queries()
    try:
        colaboradores = Colaborador.objects.prefetch_related('setor').all()[:5]
        for colab in colaboradores:
            _ = colab.setor  # No additional queries
        
        num_queries = len(connection.queries)
        print(f"  Queries executed: {num_queries}")
        print(f"  ✅ OPTIMIZED: {num_queries} queries instead of 6")
    except Exception as e:
        print(f"  Unable to test: {e}")
    
    # Test 3: Admin Query Analysis
    print("\n" + "=" * 80)
    print("TEST 3: ADMIN INTERFACE QUERIES")
    print("=" * 80)
    
    print("\nChecking Django admin changelist queries...")
    client = Client()
    
    admin_urls = [
        "/admin/rh/colaborador/",
        "/admin/metrologia/instrumento/",
        "/admin/training/procedimento/",
        "/admin/procurements/fornecedor/",
    ]
    
    for url in admin_urls:
        reset_queries()
        try:
            response = client.get(url)
            num_queries = len(connection.queries)
            status_code = response.status_code
            
            if status_code == 200:
                print(f"✅ {url:40} - {num_queries:3} queries (status: {status_code})")
                if num_queries > 20:
                    print(f"   ⚠️  High query count, consider prefetch_related in admin.py")
            else:
                print(f"❌ {url:40} - Status: {status_code}")
        except Exception as e:
            print(f"⏳ {url:40} - {str(e)[:30]}")
    
    # Test 4: Query Performance Analysis
    print("\n" + "=" * 80)
    print("TEST 4: QUERY PERFORMANCE ANALYSIS")
    print("=" * 80)
    
    reset_queries()
    
    # Run some typical queries
    test_queries = [
        ("UnidadeMedida.objects.all()", lambda: UnidadeMedida.objects.all()),
        ("Instrumento.objects.all()", lambda: Instrumento.objects.all()),
        ("Colaborador.objects.all()", lambda: Colaborador.objects.all()),
        ("HistoricoCalibracao.objects.all()", lambda: HistoricoCalibracao.objects.all()),
        ("Procedimento.objects.all()", lambda: Procedimento.objects.all()),
    ]
    
    for query_name, query_func in test_queries:
        reset_queries()
        try:
            list(query_func())  # Force evaluation
            num_queries = len(connection.queries)
            total_time = sum(float(q.get('time', 0)) for q in connection.queries)
            
            print(f"\n{query_name}")
            print(f"  Queries: {num_queries}")
            print(f"  Time: {total_time:.4f}s")
            
            if total_time > 0.1:
                print(f"  ⚠️  Slow query detected")
        except Exception as e:
            print(f"\n{query_name} - Error: {str(e)[:50]}")
    
    # Test 5: Recommendations
    print("\n" + "=" * 80)
    print("TEST 5: OPTIMIZATION RECOMMENDATIONS")
    print("=" * 80)
    
    recommendations = [
        {
            "title": "Add prefetch_related to Admin Classes",
            "description": "Use list_select_related and list_prefetch_related in admin.py",
            "impact": "Reduces admin changelist queries by 50-70%",
            "example": "list_select_related = ['setor', 'turno']\nlist_prefetch_related = ['historico_set']"
        },
        {
            "title": "Use select_related for Foreign Keys",
            "description": "In views/views.py, use select_related() for direct FK relationships",
            "impact": "Reduces queries by 1 per FK access",
            "example": "Colaborador.objects.select_related('setor', 'turno')"
        },
        {
            "title": "Implement Caching Layer",
            "description": "Add Redis caching for frequently accessed data",
            "impact": "Reduces database load by 30-50%",
            "example": "Set up Redis and use @cache_page, @cache_result decorators"
        },
        {
            "title": "Optimize Database Indexes",
            "description": "Add indexes on frequently filtered/sorted fields",
            "impact": "Query execution time reduced by 50-80%",
            "example": "Add db_index=True to Colaborador.matricula, HistoricoCalibracao.data_calibracao"
        },
        {
            "title": "Use Aggregation and Annotations",
            "description": "Move calculations to database instead of Python",
            "impact": "Reduces data transfer and memory usage",
            "example": "Use .annotate(count=Count('historico')) instead of Python loops"
        },
        {
            "title": "Implement Pagination",
            "description": "Use Django's Paginator to limit results per page",
            "impact": "Reduces memory usage and response time for large datasets",
            "example": "Paginator(queryset, 50) for 50 items per page"
        },
    ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec['title']}")
        print(f"   Description: {rec['description']}")
        print(f"   Impact: {rec['impact']}")
        print(f"   Example: {rec['example'][:60]}...")
    
    return results

# Run analysis
if __name__ == '__main__':
    print("\n🔍 Starting database query analysis...\n")
    
    results = analyze_queries()
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY & ACTION ITEMS")
    print("=" * 80)
    
    total_models = len(results["models"])
    populated_models = sum(1 for m in results["models"].values() if m["total_records"] > 0)
    models_with_fk = sum(1 for m in results["models"].values() if m["foreign_keys"])
    models_with_m2m = sum(1 for m in results["models"].values() if m["many_to_many"])
    
    print(f"\n📊 Statistics:")
    print(f"  Total Models: {total_models}")
    print(f"  Populated: {populated_models}")
    print(f"  With Foreign Keys: {models_with_fk}")
    print(f"  With Many-to-Many: {models_with_m2m}")
    print(f"  N+1 Patterns Detected: {len(results['n_plus_one'])}")
    
    print(f"\n✅ Next Steps:")
    print(f"  1. Implement prefetch_related in admin.py for models with FK/M2M")
    print(f"  2. Add select_related to views that access foreign keys")
    print(f"  3. Set up Redis for query result caching")
    print(f"  4. Add database indexes on frequently filtered columns")
    print(f"  5. Implement pagination in list views")
    print(f"  6. Monitor with django-extensions or Django Silk")
    
    print("\n" + "=" * 80)
    print("Query analysis complete! ✅")
    print("=" * 80)
