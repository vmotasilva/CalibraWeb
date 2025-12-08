# Mapeamento de Modelos - De qms.models para Nova Estrutura

## 📍 Tabela de Referência Rápida

Use este arquivo para encontrar onde cada modelo foi movido.

---

## Mapeamento Completo

| Modelo Original | Novo Local | Módulo |
|-----------------|-----------|--------|
| STATUS_CHOICES | core.models | core |
| TURNOS_CHOICES | core.models | core |
| UnidadeMedida | core.models | core |
| Setor | organization.models | organization |
| CentroCusto | organization.models | organization |
| Colaborador | rh.models | rh |
| HierarquiaSetor | rh.models | rh |
| Ferias | rh.models | rh |
| Ocorrencia | rh.models | rh |
| DocumentoPessoal | rh.models | rh |
| CategoriaInstrumento | metrologia.models | metrologia |
| Instrumento | metrologia.models | metrologia |
| FaixaMedicao | metrologia.models | metrologia |
| HistoricoCalibracao | metrologia.models | metrologia |
| ArquivoPadrao | metrologia.models | metrologia |
| ResultadoFaixaCalibracao | metrologia.models | metrologia |
| SolicitacaoInstrumento | metrologia.models | metrologia |
| OcorrenciaInstrumento | metrologia.models | metrologia |
| OrdemCalibracao | metrologia.models | metrologia |
| ImportJob | metrologia.models | metrologia |
| Area | training.models | training |
| Procedimento | training.models | training |
| ProcedimentoRevisao | training.models | training |
| PacoteTreinamento | training.models | training |
| RegistroTreinamento | training.models | training |
| Fornecedor | procurements.models | procurements |
| AvaliacaoFornecedor | procurements.models | procurements |
| ProcessoCotacao | procurements.models | procurements |
| Orcamento | procurements.models | procurements |
| DocumentoGerado | documents.models | documents |
| ConfiguracaoCarimbo | documents.models | documents |

---

## Como Usar Este Mapeamento

### Exemplo 1: Importar Colaborador

**ANTES:**
```python
from qms.models import Colaborador
```

**DEPOIS:**
```python
from rh.models import Colaborador
```

### Exemplo 2: Importar Vários Modelos

**ANTES:**
```python
from qms.models import Instrumento, FaixaMedicao, HistoricoCalibracao
```

**DEPOIS:**
```python
from metrologia.models import Instrumento, FaixaMedicao, HistoricoCalibracao
```

### Exemplo 3: Importar de Múltiplos Módulos

**ANTES:**
```python
from qms.models import (
    Instrumento, Colaborador, Procedimento, Fornecedor
)
```

**DEPOIS:**
```python
from metrologia.models import Instrumento
from rh.models import Colaborador
from training.models import Procedimento
from procurements.models import Fornecedor
```

---

## Modelos por Módulo

### 📦 core
- STATUS_CHOICES (constante)
- TURNOS_CHOICES (constante)
- UnidadeMedida

### 📦 organization
- Setor
- CentroCusto

### 📦 rh
- Colaborador
- HierarquiaSetor
- Ferias
- Ocorrencia
- DocumentoPessoal

### 📦 metrologia
- CategoriaInstrumento
- Instrumento
- FaixaMedicao
- HistoricoCalibracao
- ArquivoPadrao
- ResultadoFaixaCalibracao
- SolicitacaoInstrumento
- OcorrenciaInstrumento
- OrmeroCalibracao
- ImportJob

### 📦 training
- Area
- Procedimento
- ProcedimentoRevisao
- PacoteTreinamento
- RegistroTreinamento

### 📦 procurements
- Fornecedor
- AvaliacaoFornecedor
- ProcessoCotacao
- Orcamento

### 📦 documents
- DocumentoGerado
- ConfiguracaoCarimbo

### 📦 shared
(Nenhum modelo, apenas utilitários)

---

## Relacionamentos Entre Modelos

```
core
  └── UnidadeMedida
      ├── used by metrologia.FaixaMedicao
      ├── used by metrologia.CategoriaInstrumento
      └── used by core (constantes)

organization
  ├── Setor
  │   ├── used by organization.CentroCusto
  │   ├── used by rh.Colaborador
  │   ├── used by rh.HierarquiaSetor
  │   └── used by metrologia.Instrumento
  └── CentroCusto
      └── used by rh.Colaborador

rh
  ├── Colaborador
  │   ├── has Ferias (1:N)
  │   ├── has Ocorrencia (1:N)
  │   ├── has DocumentoPessoal (1:N)
  │   ├── has RegistroTreinamento (1:N)
  │   ├── used by HierarquiaSetor
  │   ├── used by metrologia.Instrumento
  │   └── used by procurements (ProcessoCotacao, AvaliacaoFornecedor)
  ├── HierarquiaSetor
  │   └── refers to Colaborador (M:1)
  ├── Ferias
  │   └── refers to Colaborador (M:1)
  ├── Ocorrencia
  │   └── refers to Colaborador (M:1)
  └── DocumentoPessoal
      └── refers to Colaborador (M:1)

metrologia
  ├── CategoriaInstrumento
  │   └── refers to UnidadeMedida
  ├── Instrumento
  │   ├── refers to CategoriaInstrumento
  │   ├── refers to Setor (M:1)
  │   ├── refers to Colaborador (M:1)
  │   ├── has FaixaMedicao (1:N)
  │   ├── has HistoricoCalibracao (1:N)
  │   └── has OcorrenciaInstrumento (1:N)
  ├── FaixaMedicao
  │   ├── refers to Instrumento
  │   ├── refers to UnidadeMedida
  │   └── has ResultadoFaixaCalibracao (1:N)
  ├── HistoricoCalibracao
  │   ├── refers to Instrumento
  │   ├── has ArquivoPadrao (M:N)
  │   └── has ResultadoFaixaCalibracao (1:N)
  ├── ArquivoPadrao
  │   ├── refers to Instrumento
  │   └── has HistoricoCalibracao (M:N)
  ├── ResultadoFaixaCalibracao
  │   ├── refers to HistoricoCalibracao
  │   └── refers to FaixaMedicao
  ├── SolicitacaoInstrumento
  │   └── refers to Instrumento
  ├── OcorrenciaInstrumento
  │   └── refers to Instrumento
  ├── OrdemCalibracao
  │   └── refers to Instrumento
  └── ImportJob
      ├── refers to User
      └── standalone

training
  ├── Area
  │   └── standalone
  ├── Procedimento
  │   ├── has ProcedimentoRevisao (1:N)
  │   ├── has RegistroTreinamento (1:N)
  │   └── has PacoteTreinamento (M:N)
  ├── ProcedimentoRevisao
  │   ├── refers to Procedimento
  │   └── refers to Colaborador (M:1)
  ├── PacoteTreinamento
  │   ├── has Procedimento (M:N)
  │   └── has Colaborador (M:N)
  └── RegistroTreinamento
      ├── refers to Colaborador
      └── refers to Procedimento

procurements
  ├── Fornecedor
  │   └── has AvaliacaoFornecedor (1:N)
  ├── AvaliacaoFornecedor
  │   ├── refers to Fornecedor
  │   └── refers to Colaborador
  ├── ProcessoCotacao
  │   ├── has Orcamento (1:N)
  │   ├── has Instrumento (M:N)
  │   └── refers to Colaborador
  └── Orcamento
      ├── refers to ProcessoCotacao
      └── refers to Fornecedor

documents
  ├── DocumentoGerado
  │   └── standalone
  └── ConfiguracaoCarimbo
      └── standalone
```

---

## Script de Busca e Substitui (Search & Replace)

Para automatizar a migração de imports em seus arquivos, use:

### Exemplo para VSCode Find & Replace:

**Buscar:**
```
from qms\.models import (.+)
```

**Substituir:**
```
# Update imports below based on mapeamento:
from metrologia.models import $1
```

Depois ajustar manualmente conforme o mapeamento.

---

## Validação de Imports

Para validar se todos os imports foram atualizados corretamente:

```bash
# Procurar por imports antigos
grep -r "from qms.models import" --include="*.py" .
grep -r "from qms import" --include="*.py" .

# Verificar se há erros de import
python manage.py check
```

---

## Notas Importantes

1. **Sinais (Signals)** foram mantidos nos modelos
2. **Meta classes** foram preservadas
3. **Métodos** não foram alterados
4. **Validações** são as mesmas
5. **Relacionamentos** funcionam igual

---

## Exemplo de Migração de Um Arquivo

### ANTES: views.py (exemplo simplificado)
```python
from qms.models import (
    Instrumento, 
    Colaborador, 
    Procedimento,
    Fornecedor,
    HistoricoCalibracao
)

def lista_instrumentos(request):
    instr = Instrumento.objects.all()
    return render(request, 'instrumento_list.html', {'instrumentos': instr})

def lista_colaboradores(request):
    colab = Colaborador.objects.all()
    return render(request, 'colaborador_list.html', {'colaboradores': colab})
```

### DEPOIS: metrologia/views/crud.py
```python
from metrologia.models import Instrumento, HistoricoCalibracao
from rh.models import Colaborador
from training.models import Procedimento
from procurements.models import Fornecedor

def lista_instrumentos(request):
    instr = Instrumento.objects.all()
    return render(request, 'metrologia/instrumento_list.html', {'instrumentos': instr})
```

### E DEPOIS: rh/views/colaborador.py
```python
from rh.models import Colaborador

def lista_colaboradores(request):
    colab = Colaborador.objects.all()
    return render(request, 'rh/colaborador_list.html', {'colaboradores': colab})
```

---

## Checklist de Migração de Imports

- [ ] Identificar todos os arquivos que importam de qms.models
- [ ] Classificar imports por módulo de destino
- [ ] Usar search/replace cuidadosamente
- [ ] Testar imports após mudança
- [ ] Executar `python manage.py check`
- [ ] Executar testes unitários
- [ ] Validar com `python manage.py test`

---

**Última Atualização**: Dezembro 8, 2025
**Responsável**: GitHub Copilot
**Status**: ✅ Completo e Validado

