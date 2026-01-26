# Phase 9 - Execution Roadmap Based on Task 1 Analysis

**Generated:** December 8, 2025  
**Based on:** TASK_1_ANALYSIS_REPORT.md  
**Total Estimated Hours:** 40-56 hours (5-7 working days)

---

## 🎯 Critical Path Summary

```
Task 1 ✅ DONE
├── Task 2: Prepare App Structure (2 hrs)
│   └── Dependencies: None
├── Task 3: Move Models (3 hrs)
│   └── Depends on: Task 2
├── Task 4: Update Imports (4 hrs)
│   └── Depends on: Task 3
├── Task 5: Create Migrations (2 hrs)
│   └── Depends on: Task 4
├── Task 6: Test & Validate (3 hrs)
│   └── Depends on: Task 5
└── Task 7-10: Enable Apps & Deploy (18-26 hrs)
    └── Depends on: Task 6
```

**Critical Milestones:**
- ✅ Task 1: Analysis Complete (15 mins)
- 📌 Task 2-3: Models Moved (5 hrs) - Unlocks everything
- 📌 Task 6: Tests Passing (3 hrs) - Validates architecture
- 🎯 Task 10: Production Ready (7+ hrs) - Final milestone

---

## 📋 Detailed Task Execution Plan

### ✅ TASK 1: Analyze Model Dependencies (COMPLETED)

**Duration:** 15 minutes  
**Status:** ✅ COMPLETE  

**What was done:**
- ✅ Created `scripts/analyze_models.py` analysis script
- ✅ Mapped all 27 models to target apps
- ✅ Identified 23 cross-app dependencies
- ✅ Detected 0 circular dependencies
- ✅ Identified 2 critical models (Colaborador, Instrumento)
- ✅ Defined migration order
- ✅ Generated TASK_1_ANALYSIS_REPORT.md

**Artifacts:**
- `TASK_1_ANALYSIS_REPORT.md` - Complete analysis
- `scripts/analyze_models.py` - Analysis script

**Success Criteria:** ✅ PASSED
- All models accounted for
- Dependencies clearly understood
- No blockers identified

---

### 📍 TASK 2: Prepare App Structure & Create Models.py Files

**Duration:** 2-3 hours  
**Dependencies:** Task 1  
**Status:** READY TO START  

**Objective:**
Create `models.py` files in each of 6 new apps (core, organization, rh, metrologia, procurements, training). These will be initially empty - just placeholders for upcoming model code.

**Apps to Create/Configure:**

| App | Location | Current State | Action |
|-----|----------|---------------|--------|
| core | `core/models.py` | 🟢 EXISTS | Add constants, UnidadeMedida |
| organization | `organization/models.py` | 🔴 MISSING | CREATE + Add 3 models |
| rh | `rh/models.py` | 🔴 MISSING | CREATE + Add 4 models |
| metrologia | `metrologia/models.py` | 🔴 MISSING | CREATE + Add 7 models |
| procurements | `procurements/models.py` | 🔴 MISSING | CREATE + Add 4 models |
| training | `training/models.py` | 🔴 MISSING | CREATE + Add 5 models |

**Step-by-Step Execution:**

**Step 1: Create empty models.py files**
```bash
# Create placeholder files
touch organization/models.py
touch rh/models.py
touch metrologia/models.py
touch procurements/models.py
touch training/models.py
```

**Step 2: Add Django imports & app_label**
```python
# In each models.py file:
from django.db import models
from django.contrib.auth.models import User

class Meta:
    app_label = 'organization'  # Adjust per app
```

**Step 3: Update `core/models.py`**
- Add constants (STATUS_CHOICES, TURNOS_CHOICES)
- Add UnidadeMedida model (copy from qms/models.py)
- Ensure it has no external dependencies

**Detailed Instructions Per App:**

#### CORE (models.py)
```python
# core/models.py - Place here for all apps to import from
STATUS_CHOICES = [("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("INSS", "Afastado INSS")]
TURNOS_CHOICES = [
    ("ADM", "Administrativo"),
    ("TURNO_1", "Turno 1"),
    ("TURNO_2", "Turno 2"),
    ("TURNO_3", "Turno 3"),
    ("12X36", "12x36"),
]

class UnidadeMedida(models.Model):
    # Copy from qms/models.py line 305
    ...
```

#### ORGANIZATION (models.py)
```python
# organization/models.py
from django.db import models
from core.models import UnidadeMedida

class Setor(models.Model):
    # Copy from qms/models.py line 31
    ...

class CentroCusto(models.Model):
    # Copy from qms/models.py line 46
    # Update FK: setor = models.ForeignKey(Setor, ...)
    ...

class HierarquiaSetor(models.Model):
    # Copy from qms/models.py line 163
    ...
```

#### RH (models.py)
```python
# rh/models.py
from django.db import models
from django.contrib.auth.models import User
from organization.models import Setor, CentroCusto
from core.models import STATUS_CHOICES, TURNOS_CHOICES

class Colaborador(models.Model):
    # Copy from qms/models.py line 70
    # ForeignKeys can use string references:
    # setor = models.ForeignKey('organization.Setor', ...)
    ...

class Ferias(models.Model):
    # Copy from qms/models.py line 210
    ...

class Ocorrencia(models.Model):
    # Copy from qms/models.py line 238
    ...

class DocumentoPessoal(models.Model):
    # Copy from qms/models.py line 281
    ...
```

#### METROLOGIA (models.py)
```python
# metrologia/models.py
from django.db import models
from django.contrib.auth.models import User
from organization.models import Setor
from rh.models import Colaborador
from core.models import UnidadeMedida, STATUS_CHOICES
from procurements.models import ProcessoCotacao

class CategoriaInstrumento(models.Model):
    # Copy from qms/models.py
    ...

class Instrumento(models.Model):
    # Copy from qms/models.py
    # Use string references:
    # setor_responsavel = models.ForeignKey('organization.Setor', ...)
    # responsavel_calibracao = models.ForeignKey('rh.Colaborador', ...)
    ...

# ... other metrologia models
```

#### PROCUREMENTS (models.py)
```python
# procurements/models.py
from django.db import models
from django.contrib.auth.models import User
from rh.models import Colaborador

class Fornecedor(models.Model):
    # Copy from qms/models.py
    ...

class AvaliacaoFornecedor(models.Model):
    # Copy from qms/models.py
    # Use string reference:
    # avaliador = models.ForeignKey('rh.Colaborador', ...)
    ...

# ... other procurements models
```

#### TRAINING (models.py)
```python
# training/models.py
from django.db import models
from rh.models import Colaborador

class Procedimento(models.Model):
    # Copy from qms/models.py
    ...

class Area(models.Model):
    # Copy from qms/models.py
    ...

class ProcedimentoRevisao(models.Model):
    # Use string reference:
    # revisor_qualidade = models.ForeignKey('rh.Colaborador', ...)
    ...

# ... other training models
```

**String References Strategy:**
To avoid circular imports, use Django's string references:
```python
# INSTEAD OF:
from rh.models import Colaborador
class Instrumento(models.Model):
    responsavel = models.ForeignKey(Colaborador, ...)

# DO THIS:
class Instrumento(models.Model):
    responsavel = models.ForeignKey('rh.Colaborador', on_delete=...)
```

**Validation Checkpoint:**
```bash
python manage.py check
# Should report: System check identified no issues (0 silenced).
```

**Success Criteria:**
- ✅ All 6 models.py files created
- ✅ Constants moved to core/models.py
- ✅ Django check passes (no errors)
- ✅ No import errors when running `python manage.py check`

---

### 📍 TASK 3: Move Models from QMS to Target Apps

**Duration:** 3-4 hours  
**Dependencies:** Task 2  
**Status:** QUEUED  

**Objective:**
Copy model definitions from `qms/models.py` (line 1-997) to respective app models.py files. Keep QMS models.py for later steps.

**Execution Plan:**

**Step 1: Extract models by app**
For each app below, copy the exact model code from qms/models.py to app/models.py:

**CORE (1 model):**
- ✅ UnidadeMedida (lines 305-314)

**ORGANIZATION (3 models):**
- ✅ Setor (lines 31-43)
- ✅ CentroCusto (lines 46-68)
- ✅ HierarquiaSetor (lines 163-207)

**RH (4 models):**
- ✅ Colaborador (lines 70-160)
- ✅ Ferias (lines 210-235)
- ✅ Ocorrencia (lines 238-278)
- ✅ DocumentoPessoal (lines 281-302)

**METROLOGIA (7 models):**
- ✅ CategoriaInstrumento (lines 316-328)
- ✅ Instrumento (lines 459-498)
- ✅ FaixaMedicao (lines 529-564)
- ✅ HistoricoCalibracao (lines 567-631)
- ✅ ArquivoPadrao (lines 634-699)
- ✅ ResultadoFaixaCalibracao (lines 702-793)
- ✅ OrdemCalibracao (lines 406-456)

**PROCUREMENTS (4 models):**
- ✅ Fornecedor (lines 796-816)
- ✅ AvaliacaoFornecedor (lines 819-842)
- ✅ ProcessoCotacao (lines 845-858)
- ✅ Orcamento (lines 861-878)

**TRAINING (5 models):**
- ✅ Procedimento (lines 881-903)
- ✅ PacoteTreinamento (lines 906-919)
- ✅ Area (lines 922-932)
- ✅ ProcedimentoRevisao (lines 935-952)
- ✅ RegistroTreinamento (lines 955-990)

**QMS (Keep as-is):**
- ✅ SolicitacaoInstrumento (lines 331-369)
- ✅ OcorrenciaInstrumento (lines 372-403)
- ✅ ImportJob (lines 501-526)

**Step 2: Fix imports in each models.py**
After copying models, ensure imports are correct:
- Use string references for cross-app ForeignKeys
- Import only from apps with models already moved
- For forward references, use string notation

**Example - metrologia/models.py imports:**
```python
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
import uuid

# Import from moved apps
from core.models import UnidadeMedida, STATUS_CHOICES
from organization.models import Setor
from rh.models import Colaborador

# For procurements.ProcessoCotacao, use string reference in FK:
# processo_cotacao = models.ForeignKey('procurements.ProcessoCotacao', ...)
```

**Step 3: Validation**
```bash
python manage.py check --deploy
# Ensure all models load correctly
```

**Success Criteria:**
- ✅ All 27 models split across 7 apps
- ✅ qms/models.py has only 3 models (SolicitacaoInstrumento, OcorrenciaInstrumento, ImportJob)
- ✅ `python manage.py check` passes
- ✅ No import errors
- ✅ `python manage.py makemigrations --dry-run` shows expected changes

---

### 📍 TASK 4: Update Imports in Views, Forms & Admin

**Duration:** 4-5 hours  
**Dependencies:** Task 3  
**Status:** QUEUED  

**Objective:**
Fix all imports across views, forms, admin, tasks, and other modules to point to correct app models.

**Files to Update:**

| File | Current Imports | Action |
|------|-----------------|--------|
| `metrologia/views.py` | `from qms.models import *` | Update to metrologia, core, organization imports |
| `rh/views.py` | `from qms.models import *` | Update to rh, organization, metrologia imports |
| `training/views.py` | `from qms.models import *` | Update to training, rh imports |
| `procurements/views.py` | `from qms.models import *` | Update to procurements, rh, metrologia imports |
| `organization/views.py` | `from qms.models import *` | Update to organization, rh imports |
| `metrologia/forms.py` | `from qms.models import *` | Update model references |
| `rh/forms.py` | `from qms.models import *` | Update model references |
| `qms/admin.py` | `from qms.models import *` | Import from appropriate apps |
| `qms/tasks.py` | `from qms.models import *` | Lazy imports for cross-app dependencies |
| `config/admin.py` | NA | Register apps with their models |

**Execution Plan:**

**Step 1: Create mapping of old → new imports**
```python
# OLD (qms/models.py)
from qms.models import Setor, CentroCusto, HierarquiaSetor

# NEW (split across apps)
from organization.models import Setor, CentroCusto, HierarquiaSetor
from rh.models import Colaborador, Ferias
from metrologia.models import Instrumento, HistoricoCalibracao
# etc.
```

**Step 2: Update each app's views.py**
Example - metrologia/views.py:
```python
# OLD
from qms.models import (
    Instrumento, HistoricoCalibracao, FaixaMedicao,
    UnidadeMedida, Colaborador, Setor
)

# NEW
from metrologia.models import (
    Instrumento, HistoricoCalibracao, FaixaMedicao
)
from core.models import UnidadeMedida
from rh.models import Colaborador
from organization.models import Setor
```

**Step 3: Update admin registrations**
In `config/admin.py` or app-level `admin.py`:
```python
# OLD
from qms.models import *
admin.site.register(Instrumento, ...)

# NEW
from metrologia.models import Instrumento
@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    ...
```

**Step 4: Handle circular imports (if any)**
For models that reference each other across apps, use lazy imports:
```python
# In tasks.py or views that need cross-app models:
def some_function():
    from metrologia.models import Instrumento  # Import inside function
    from rh.models import Colaborador
    # Use models...
```

**Step 5: Update form references**
In forms, update Meta.model references:
```python
# OLD
class InstrumentoForm(forms.ModelForm):
    class Meta:
        model = models.Instrumento

# NEW
from metrologia.models import Instrumento
class InstrumentoForm(forms.ModelForm):
    class Meta:
        model = Instrumento
```

**Validation:**
```bash
python manage.py check
python manage.py test qms.tests --verbosity=1
# All should pass
```

**Success Criteria:**
- ✅ All imports updated
- ✅ `python manage.py check` passes
- ✅ All 30 tests still passing
- ✅ No "ModuleNotFoundError" or "ImportError" in logs

---

### 📍 TASK 5: Create & Run Django Migrations

**Duration:** 2-3 hours  
**Dependencies:** Task 4  
**Status:** QUEUED  

**Objective:**
Create Django migrations to reflect the new model structure. Models are being moved but database state should remain unchanged.

**Execution Plan:**

**Step 1: Generate migrations**
```bash
python manage.py makemigrations --dry-run --verbosity=3
```

This will show:
- Migrations for new apps (core, organization, rh, metrologia, procurements, training)
- Changes in qms (3 models remaining vs 27 before)
- Model moves (Django may detect this)

**Step 2: Review migration plan**
Before applying, check:
- ✅ No data loss indicated
- ✅ No manual migrations needed
- ✅ All ForeignKey references intact

**Step 3: Create migrations**
```bash
python manage.py makemigrations
```

**Step 4: Review generated migration files**
Check the generated migration files in each app's `migrations/` folder:
- `core/migrations/0001_initial.py`
- `organization/migrations/0001_initial.py`
- `rh/migrations/0001_initial.py`
- etc.

**Step 5: Test migrations**
```bash
python manage.py migrate --plan
# Should show expected migration sequence

python manage.py migrate
# Apply migrations
```

**Step 6: Validate migration result**
```bash
python manage.py check
python manage.py test qms.tests
```

**Success Criteria:**
- ✅ All migrations created without errors
- ✅ `python migrate` succeeds
- ✅ `python manage.py check` shows no issues
- ✅ All 30 tests still passing
- ✅ Database state unchanged (same models accessible)

---

### 📍 TASK 6: Test & Validate Architecture

**Duration:** 2-3 hours  
**Dependencies:** Task 5  
**Status:** QUEUED  

**Objective:**
Ensure all 30 tests pass with new architecture and no import/dependency issues.

**Execution Plan:**

**Step 1: Run full test suite**
```bash
python manage.py test qms.tests --verbosity=2
```

Expected: ✅ 30/30 passing

**Step 2: Run specific test classes**
```bash
python manage.py test qms.tests.OcorrenciaTests
python manage.py test qms.tests.CeleryTasksTests
python manage.py test qms.tests.ImportInstrumentsTaskTests
# etc - all test classes
```

**Step 3: Check for import issues**
```bash
python manage.py shell
>>> from metrologia.models import Instrumento
>>> from rh.models import Colaborador
>>> from organization.models import Setor
>>> from training.models import Procedimento
>>> # etc - verify all imports work
>>> exit()
```

**Step 4: Django admin check**
```bash
python manage.py runserver
# Visit http://localhost:8000/admin/
# Verify all models show correctly in admin
```

**Step 5: Run security checks**
```bash
python manage.py check --deploy
bandit -r . --exclude .venv,migrations
safety check
```

**Success Criteria:**
- ✅ All 30 tests passing
- ✅ No import errors
- ✅ Django admin shows all models correctly
- ✅ Security checks: 0 critical issues
- ✅ No circular import warnings

---

### 📍 TASK 7: Re-enable 8 Modular Apps

**Duration:** 2 hours  
**Dependencies:** Task 6  
**Status:** QUEUED  

**Objective:**
Add the 8 modular apps back to INSTALLED_APPS now that models are properly distributed.

**Execution Plan:**

**Step 1: Update config/settings.py**
```python
# In INSTALLED_APPS, uncomment/add:
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Project Apps (Core)
    'qms',
    
    # Project Apps (Modular) - NOW RE-ENABLED
    'core',
    'organization',
    'rh',
    'metrologia',
    'procurements',
    'training',
    'documents',
    'shared',
    
    # Third-party
    'rest_framework',
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
]
```

**Step 2: Update config/urls.py**
Restore URL patterns for all apps:
```python
# In config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Re-enable modular URLs
    path('metrologia/', include('metrologia.urls')),
    path('rh/', include('rh.urls')),
    path('training/', include('training.urls')),
    path('organization/', include('organization.urls')),
    path('procurements/', include('procurements.urls')),
    path('documents/', include('documents.urls')),
    path('shared/', include('shared.urls')),
    
    # Static/Media
    path('static/', ...),
    path('media/', ...),
]
```

**Step 3: Validate**
```bash
python manage.py check
python manage.py test qms.tests
```

**Success Criteria:**
- ✅ All 8 apps in INSTALLED_APPS
- ✅ `python manage.py check` passes (0 issues)
- ✅ 30 qms tests still passing
- ✅ No "AppNotFound" errors

---

### 📍 TASK 8: Enable All Tests & Reach Coverage Goal

**Duration:** 3-4 hours  
**Dependencies:** Task 7  
**Status:** QUEUED  

**Objective:**
Uncomment the 55+ tests that were disabled in Task 1, enable them, and reach 85+ total tests passing with 70%+ coverage.

**Execution Plan:**

**Step 1: Uncomment view tests**
In `qms/tests.py`:
- Uncomment BasicViewsTests (3 tests)
- Uncomment ProcedimentosListViewTests (5 tests)

**Step 2: Add tests for other app modules**
Create test files:
- `organization/tests.py` (5 tests)
- `rh/tests.py` (10 tests)
- `metrologia/tests.py` (15 tests)
- `procurements/tests.py` (8 tests)
- `training/tests.py` (12 tests)
- `documents/tests.py` (5 tests)

**Step 3: Run full test suite**
```bash
python manage.py test --verbosity=1
# Should show: Ran 85+ tests, OK
```

**Step 4: Check coverage**
```bash
coverage run --source='.' manage.py test
coverage report
# Should show 70%+ coverage
```

**Success Criteria:**
- ✅ 85+ total tests (55+ new + 30 qms)
- ✅ 100% test pass rate
- ✅ 70%+ code coverage
- ✅ All app tests passing

---

### 📍 TASK 9: Security Scan & Code Quality

**Duration:** 1-2 hours  
**Dependencies:** Task 8  
**Status:** QUEUED  

**Objective:**
Run security scans and code quality checks. Ensure 0 critical issues.

**Execution Plan:**

**Step 1: Run Bandit (security)**
```bash
bandit -r . --exclude .venv,migrations -f json > security-report.json
# Should show: 0 HIGH severity issues
```

**Step 2: Run Safety (dependencies)**
```bash
safety check --json > safety-report.json
# Should show: 0 critical vulnerabilities
```

**Step 3: Run code formatters**
```bash
black --check .
isort --check-only .
```

**Step 4: Run linters**
```bash
flake8 . --exclude .venv,migrations --max-line-length=120
```

**Success Criteria:**
- ✅ Bandit: 0 HIGH severity
- ✅ Safety: 0 critical vulnerabilities
- ✅ Code format valid
- ✅ Linting: 0 errors (warnings acceptable)

---

### 📍 TASK 10: Production Deployment & Final Validation

**Duration:** 3-4 hours  
**Dependencies:** Task 9  
**Status:** QUEUED  

**Objective:**
Final validation, documentation, and deploy to production environment.

**Execution Plan:**

**Step 1: Create production checklist**
- ✅ Database migrations applied
- ✅ Static files collected
- ✅ Environment variables configured
- ✅ Secrets not in repo
- ✅ Database backups created

**Step 2: Staging deployment**
```bash
# Deploy to staging environment (e.g., Railway staging branch)
git push origin develop
# Wait for CI/CD to deploy
```

**Step 3: Test staging**
```bash
# Verify all functionality works in staging
curl https://staging.calibraweb.com/api/health/
curl https://staging.calibraweb.com/metrologia/instruments/
# etc - test all endpoints
```

**Step 4: Production deployment**
```bash
# If staging tests pass, deploy to production
git push origin main
# Wait for CI/CD to deploy
```

**Step 5: Production validation**
```bash
# Final checks
curl https://calibraweb.com/api/health/
python manage.py test --no-input
python manage.py migrate --no-input
```

**Success Criteria:**
- ✅ All systems operational in production
- ✅ No errors in logs
- ✅ Performance metrics normal
- ✅ User tests passing
- ✅ Database integrity verified

---

## 📊 Timeline & Resource Allocation

### Calendar Schedule (Realistic)

```
Week 1 (Mon-Fri)
Mon:  Task 1 (done)  + Task 2-3 (4 hrs)  [Prepare structure + move models]
Tue:  Task 3-4 (6 hrs)                   [Move remaining + update imports]
Wed:  Task 4-5 (6 hrs)                   [Complete imports + create migrations]
Thu:  Task 6-7 (4 hrs)                   [Test + re-enable apps]
Fri:  Task 8-9 (6 hrs)                   [Enable tests + security scan]

Week 2 (Mon)
Mon:  Task 10 (3-4 hrs)                  [Production deployment]
```

### Hours Per Task

| Task | Est. Hours | Actual | Status |
|------|-----------|--------|--------|
| 1 | 1 | 0.25 | ✅ Done |
| 2 | 2-3 | TBD | 📋 Queued |
| 3 | 3-4 | TBD | 📋 Queued |
| 4 | 4-5 | TBD | 📋 Queued |
| 5 | 2-3 | TBD | 📋 Queued |
| 6 | 2-3 | TBD | 📋 Queued |
| 7 | 2 | TBD | 📋 Queued |
| 8 | 3-4 | TBD | 📋 Queued |
| 9 | 1-2 | TBD | 📋 Queued |
| 10 | 3-4 | TBD | 📋 Queued |
| **TOTAL** | **25-35** | - | **🎯 On Track** |

---

## 🚀 Next Immediate Steps

1. **Review Analysis:** Read TASK_1_ANALYSIS_REPORT.md (5 mins)
2. **Start Task 2:** Create models.py files (15 mins setup)
3. **Execute Task 3:** Move models (2-3 hours of careful copying)
4. **Validate:** Run `python manage.py check` after each major step

---

## 📝 Notes & Assumptions

- ✅ Django 5.2 supports lazy string references perfectly
- ✅ No manual intervention needed for FK cascades
- ✅ Database schema won't change (models just reorganized)
- ✅ All tests designed to pass with new structure
- ⚠️ Task ordering is CRITICAL - cannot skip ahead
- ⚠️ Backup database before applying migrations
- ⚠️ Review each migration before applying to production

---

## ✨ Success Criteria Summary

**Phase 9 is complete when:**
- ✅ 27 models distributed across 7 apps correctly
- ✅ 85+ total tests passing (100%)
- ✅ 70%+ code coverage
- ✅ 0 circular dependencies
- ✅ 0 import errors
- ✅ Bandit: 0 critical issues
- ✅ Safety: 0 critical vulnerabilities
- ✅ All 8 modular apps re-enabled
- ✅ All routes working
- ✅ Production deployment successful

---

**This roadmap is based on detailed analysis and should be followed sequentially. Each task unlocks the next.**

