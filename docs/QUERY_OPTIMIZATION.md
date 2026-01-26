# 📈 Query Optimization - Fase 6 Task #2

**Data:** 09 de Dezembro de 2025  
**Status:** ✅ IMPLEMENTANDO  
**Task:** #2  
**Commits:** TBD

---

## 🎯 Objetivo

Otimizar queries N+1 e relacionamentos através de `select_related()` e `prefetch_related()`, reduzindo **50-80%** do número de queries por página.

---

## 🔍 Problema: N+1 Queries

### Exemplo Problemático
```python
# Views mal otimizado (RUIM ❌)
def listar_instrumentos_view(request):
    instrumentos = Instrumento.objects.all()  # 1 query
    
    for instrumento in instrumentos:  # Para cada instrumento
        print(instrumento.categoria.nome)    # +1 query (N queries extras!)
        print(instrumento.setor.nome)        # +1 query
        print(instrumento.responsavel.nome_completo)  # +1 query
    
    # Total: 1 + (N * 3) queries = 1 + (50 * 3) = 151 queries! ❌
```

### Solução: Eager Loading
```python
# Views otimizado (BOM ✅)
def listar_instrumentos_view(request):
    instrumentos = (Instrumento.objects
        .select_related('categoria')      # FK: 1 query adicional
        .select_related('setor')          # FK: 1 query adicional
        .select_related('responsavel')    # FK: 1 query adicional
        .prefetch_related('historicos')   # Reverse FK: 1 query
    )
    
    for instrumento in instrumentos:
        print(instrumento.categoria.nome)
        print(instrumento.setor.nome)
        print(instrumento.responsavel.nome_completo)
    
    # Total: 1 + 3 + 1 = 5 queries! ✅ (30x melhor!)
```

---

## 📊 Queries Identificadas e Otimizadas

### 1. Listar Instrumentos Ativos

**ANTES:**
```python
# qms/views.py - listar_instrumentos_view
instrumentos = Instrumento.objects.filter(ativo=True)

# Resultado:
# - 1 query: SELECT * FROM qms_instrumento WHERE ativo=TRUE
# - N queries: SELECT * FROM qms_categoria WHERE id=X
# - N queries: SELECT * FROM qms_setor WHERE id=Y
# - Total: 1 + (50 * 2) = 101 queries
```

**DEPOIS:**
```python
# Otimizado com select_related
instrumentos = (Instrumento.objects
    .filter(ativo=True)
    .select_related('categoria')
    .select_related('setor')
    .select_related('responsavel')
)

# Resultado:
# - 1 query principal + 3 JOINs
# - Total: 1 query
```

**Melhoria:** 101x → 1 query (101x melhor!) ⚡

---

### 2. Histórico de Calibração por Instrumento

**ANTES:**
```python
# Views mal otimizado
instrumento = Instrumento.objects.get(id=1)

# Template precisa acessar histórico
{% for hist in instrumento.historicos.all %}
    {{ hist.data_calibracao }}
    {{ hist.fornecedor }}
{% endfor %}

# Resultado:
# - 1 query: GET instrumento
# - 1 query: GET historicos
# - Total: 2 queries
```

**DEPOIS:**
```python
# Otimizado com prefetch_related
instrumento = (Instrumento.objects
    .prefetch_related('historicos')
    .get(id=1)
)

# Resultado:
# - 1 query: GET instrumento
# - 1 query: GET todos os historicos em batch
# - Total: 2 queries (mas muito mais rápido!)
```

---

### 3. Exportar Instrumentos com Relacionamentos

**ANTES:**
```python
# ExportadorInstrumentos (RUIM)
instrumentos = Instrumento.objects.all()  # 1 query

for instr in instrumentos:
    categoria = instr.categoria.nome     # +1 query cada
    setor = instr.setor.nome             # +1 query cada
    
# Total: 1 + (50 * 2) = 101 queries
```

**DEPOIS:**
```python
# ExportadorInstrumentos (BOM)
instrumentos = (Instrumento.objects
    .select_related('categoria', 'setor', 'responsavel')
)

for instr in instrumentos:
    categoria = instr.categoria.nome     # Já em memória!
    setor = instr.setor.nome             # Já em memória!

# Total: 4 queries (categoria join, setor join, etc)
```

**Melhoria:** 101 → 4 queries (25x melhor!) ⚡

---

## 🛠️ Implementação: Utility Module

**Arquivo:** `qms/utils/query_optimizer.py`

```python
# QueryOptimizer com métodos reutilizáveis
class InstrumentoQueryOptimizer:
    """Otimiza queries de Instrumento com eager loading."""
    
    @staticmethod
    def listar_completo():
        """Retorna queryse otimizado para listagem."""
        return (Instrumento.objects
            .select_related('categoria', 'setor', 'responsavel')
            .prefetch_related('historicos', 'faixas')
        )
    
    @staticmethod
    def por_filtros(filtros_dict):
        """Aplica filtros dinamicamente em query otimizada."""
        qs = InstrumentoQueryOptimizer.listar_completo()
        
        if 'categoria' in filtros_dict:
            qs = qs.filter(categoria=filtros_dict['categoria'])
        if 'setor' in filtros_dict:
            qs = qs.filter(setor=filtros_dict['setor'])
        if 'ativo' in filtros_dict:
            qs = qs.filter(ativo=filtros_dict['ativo'])
            
        return qs
```

---

## 📋 Views Otimizadas

### View 1: listar_instrumentos_view
```python
# ANTES
def listar_instrumentos_view(request):
    instrumentos = Instrumento.objects.filter(ativo=True)

# DEPOIS
def listar_instrumentos_view(request):
    instrumentos = (Instrumento.objects
        .filter(ativo=True)
        .select_related('categoria', 'setor', 'responsavel')
        .prefetch_related('historicos')
    )
```

### View 2: detalhe_instrumento_view
```python
# ANTES
def detalhe_instrumento_view(request, instrumento_id):
    instrumento = Instrumento.objects.get(id=instrumento_id)

# DEPOIS
def detalhe_instrumento_view(request, instrumento_id):
    instrumento = (Instrumento.objects
        .select_related('categoria', 'setor', 'responsavel')
        .prefetch_related('historicos', 'faixas')
        .get(id=instrumento_id)
    )
```

### View 3: exportadores (Excel, CSV, PDF)
```python
# ANTES
class ExportadorInstrumentos:
    def exportar_excel(self, queryset):
        # queryset.all() sem otimizações
        
# DEPOIS
class ExportadorInstrumentos:
    def exportar_excel(self, queryset):
        # Apply optimizations automatically
        queryset = queryset.select_related(
            'categoria', 'setor', 'responsavel'
        )
        queryset = queryset.prefetch_related('historicos')
```

---

## 📈 Padrões de Otimização

### Padrão 1: only() e defer()

**Quando usar:**  
- `only()`: Você só precisa de alguns campos
- `defer()`: Você não precisa de alguns campos (geralmente texto grande)

```python
# Buscar apenas campos necessários para listagem
Instrumento.objects.only(
    'id', 'tag', 'descricao', 'ativo',
    'categoria__nome', 'setor__nome'
)

# Evitar campos heavy (TextField)
HistoricoCalibracao.objects.defer('observacoes')
```

### Padrão 2: prefetch_related com Prefetch()

**Para queries mais complexas:**

```python
from django.db.models import Prefetch

# Prefetch apenas históricos aprovados
queryset = Prefetch(
    'historicos',
    HistoricoCalibracao.objects
        .filter(resultado='APROVADO_SEM_CORRECAO')
        .order_by('-data_calibracao')[:5]
)

instrumentos = Instrumento.objects.prefetch_related(queryset)
```

### Padrão 3: values() para queries read-only

```python
# Para relatórios/exports que não precisam de objetos
Instrumento.objects.values(
    'id', 'tag', 'descricao', 
    'categoria__nome', 'setor__nome'
)
# Mais rápido pois retorna dicts, não objetos!
```

---

## 🧪 Testes de Performance

### Benchmark Script

```python
# qms/management/commands/benchmark_queries.py
import time
from django.core.management.base import BaseCommand
from qms.models import Instrumento

class Command(BaseCommand):
    def handle(self, *args, **options):
        # ANTES (sem otimizar)
        start = time.time()
        with django.test.utils.CaptureQueriesContext(connection) as ctx:
            instrumentos = Instrumento.objects.filter(ativo=True)
            for instr in instrumentos:
                _ = instr.categoria.nome
                _ = instr.setor.nome
        antes_time = time.time() - start
        antes_queries = len(ctx)
        
        # DEPOIS (com otimizar)
        start = time.time()
        with django.test.utils.CaptureQueriesContext(connection) as ctx:
            instrumentos = (Instrumento.objects
                .filter(ativo=True)
                .select_related('categoria', 'setor')
            )
            for instr in instrumentos:
                _ = instr.categoria.nome
                _ = instr.setor.nome
        depois_time = time.time() - start
        depois_queries = len(ctx)
        
        self.stdout.write(f"ANTES:  {antes_queries} queries, {antes_time:.3f}s")
        self.stdout.write(f"DEPOIS: {depois_queries} queries, {depois_time:.3f}s")
        self.stdout.write(f"Melhoria: {antes_queries/depois_queries:.1f}x")
```

---

## ✅ Checklist de Implementação

- [ ] Criar `qms/utils/query_optimizer.py`
- [ ] Criar `qms/management/commands/benchmark_queries.py`
- [ ] Otimizar `listar_instrumentos_view`
- [ ] Otimizar `detalhe_instrumento_view`
- [ ] Otimizar `ExportadorInstrumentos`
- [ ] Otimizar `ExportadorEstatisticas`
- [ ] Otimizar `views_treinamentos.py`
- [ ] Testar todas as views
- [ ] Documentar padrões
- [ ] Rodar benchmark (antes/depois)
- [ ] Verificar com Django Debug Toolbar
- [ ] Commit

---

## 📚 Resultado Esperado

| View | Antes | Depois | Melhoria |
|------|-------|--------|----------|
| listar_instrumentos | 100 queries | 4 queries | 25x |
| detalhe_instrumento | 15 queries | 4 queries | 3.75x |
| exportar_excel | 150 queries | 5 queries | 30x |
| filtrar_e_exportar | 200 queries | 6 queries | 33x |

**TOTAL:** Média 15-30x menos queries ⚡

---

**Status:** 🔄 EM DESENVOLVIMENTO  
**Próxima:** Implementar otimizações nas views

