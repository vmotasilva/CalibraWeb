# Models Distribution Analysis - Phase 6

## Current State: Models are ALREADY DISTRIBUTED!

The refactoring has been partially completed. Models are already in their appropriate modules:

### ✅ Core Module (core/models/)
- UnidadeMedida
- Constants: STATUS_CHOICES, TURNOS_CHOICES

### ✅ Organization Module (organization/models/)
- Setor
- CentroCusto

### ✅ RH Module (rh/models/)
- Colaborador
- HierarquiaSetor
- Ferias
- DocumentoPessoal
- PacoteTreinamento

### ✅ Metrologia Module (metrologia/models/)
- CategoriaInstrumento
- Instrumento
- FaixaMedicao
- HistoricoCalibracao
- ArquivoPadrao
- ResultadoFaixaCalibracao

### ✅ Training Module (training/models/)
- Procedimento
- ProcedimentoRevisao
- RegistroTreinamento
- Area

### ✅ Procurements Module (procurements/models/)
- Fornecedor
- AvaliacaoFornecedor
- ProcessoCotacao
- Orcamento

### ⚠️ STILL IN QMS (deprecated/shared):
- Ocorrencia - Needs to stay in qms.models (referenced by both rh and metrologia)
- SolicitacaoInstrumento - Needs to stay in qms.models (cross-module dependency)
- ImportJob - Needs to stay in qms.models (utility model for imports)

---

## Task: Fix All Imports

The task is to update all Python files that import from `qms.models` to import from the correct module instead.

### Files to Update:

#### 1. metrologia/views/views.py (Line 33-38)
- FROM: `from qms.models import (Instrumento, FaixaMedicao, HistoricoCalibracao, CategoriaInstrumento, Setor, Colaborador, ImportJob, SolicitacaoInstrumento, ResultadoFaixaCalibracao, ArquivoPadrao, UnidadeMedida)`
- TO: Multiple imports from different modules
  - `from metrologia.models import (Instrumento, FaixaMedicao, HistoricoCalibracao, CategoriaInstrumento, ResultadoFaixaCalibracao, ArquivoPadrao)`
  - `from organization.models import Setor`
  - `from rh.models import Colaborador`
  - `from core.models import UnidadeMedida`
  - `from qms.models import ImportJob, SolicitacaoInstrumento` (stay here)

#### 2. rh/views/views.py (Line 16-18)
- FROM: `from qms.models import (Colaborador, HierarquiaSetor, Setor, CentroCusto)`
- TO:
  - `from rh.models import Colaborador, HierarquiaSetor`
  - `from organization.models import Setor, CentroCusto`

#### 3. training/views/views.py (Line 20 and dynamics)
- FROM: `from qms.models import Procedimento, RegistroTreinamento, Colaborador`
- TO:
  - `from training.models import Procedimento, RegistroTreinamento`
  - `from rh.models import Colaborador`

#### 4. shared/views/views.py (Line 22-25)
- FROM: `from qms.models import (Instrumento, SolicitacaoInstrumento, ProcessoCotacao, ImportJob, Colaborador, CentroCusto, RegistroTreinamento)`
- TO: Multiple imports from different modules
  - `from metrologia.models import Instrumento`
  - `from procurements.models import ProcessoCotacao`
  - `from training.models import RegistroTreinamento`
  - `from rh.models import Colaborador`
  - `from organization.models import CentroCusto`
  - `from qms.models import SolicitacaoInstrumento, ImportJob` (stay here)

#### 5. procurements/views/views.py (Line 17)
- FROM: `from qms.models import ImportJob`
- TO: `from qms.models import ImportJob` (stay the same - shared model)

#### 6. procurements/forms/forms.py (Line 7)
- FROM: `from qms.models import SolicitacaoInstrumento`
- TO: `from qms.models import SolicitacaoInstrumento` (stay the same - shared model)

#### 7. rh/forms/forms.py (Line 8)
- FROM: `from qms.models import Ocorrencia`
- TO: `from qms.models import Ocorrencia` (stay the same - shared model)

#### 8. qms/views_helpers.py (Lines 88, 207)
- FROM: `from qms.models import Colaborador, HierarquiaSetor`
- TO: `from rh.models import Colaborador, HierarquiaSetor`

#### 9. Scripts to Update:
- scripts/importar_procedimentos_shell.py
- scripts/importar_procedimentos_excel.py
- scripts/importar_procedimentos.py
- scripts/gerar_registros_treinamento.py
- qms/management/commands/*.py (14 files)

---

## Implementation Plan

1. Update view imports (5 files) - CRITICAL
2. Update form imports (1 file)
3. Update helpers (1 file)
4. Update scripts (4 files)
5. Update management commands (14 files)

Total files to update: ~25

---

## Models That Must Stay in qms.models:

1. **Ocorrencia** - referenced by both metrologia and rh
2. **SolicitacaoInstrumento** - cross-module dependency (procurements/metrologia)
3. **ImportJob** - utility model used by multiple modules

These could be moved to a "shared" app if needed later, but for now keeping them in qms makes sense as they're utilities/shared models.
