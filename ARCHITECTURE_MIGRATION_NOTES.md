# Architecture Migration Notes

**Status:** Architecture Refactoring Phase - Model Consolidation Pending

## Current Situation

The CalibraWeb project underwent a significant architectural refactoring in Phase 8 to modularize the monolithic QMS application into independent modules:

- `core/` - System base models and constants
- `organization/` - Organizational structure
- `rh/` - Human resources
- `metrologia/` - Metrology and instrumentation
- `training/` - Training management
- `procurements/` - Procurement management
- `documents/` - Document management
- `shared/` - Shared utilities

## Problem: Model Duplication

### Issue
The legacy `qms/` module still contains ALL the models. The new modular apps (metrologia, rh, organization, etc.) were created with copies of these models for the refactoring.

### Current State
- **qms/** - Contains ALL models (legacy monolith)
  - Colaborador, Setor, Ferias, HierarquiaSetor
  - Instrumento, FaixaMedicao, HistoricoCalibracao, UnidadeMedida
  - Procedimento, RegistroTreinamento, Area, PacoteTreinamento
  - Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento
  - Ocorrencia, OcorrenciaInstrumento, DocumentoPessoal, SolicitacaoInstrumento
  - ImportJob, ArquivoPadrao, ResultadoFaixaCalibracao

- **New Modules** - Created with views, forms, utils (models disabled)
  - core.models (EMPTY - models in qms)
  - rh.models (EMPTY - models in qms)
  - metrologia.models (EMPTY - models in qms)
  - training.models (EMPTY - models in qms)
  - procurements.models (EMPTY - models in qms)
  - organization.models (EMPTY - models in qms)
  - documents.models (EMPTY - models in qms)
  - shared.models (EMPTY - models in qms)

### Configuration
`config/settings.py` - `INSTALLED_APPS` has all modular apps DISABLED to prevent model clash errors:

```python
# Novos módulos modulares (DESATIVADOS - duplicam modelos com qms)
# "core.apps.CoreConfig",
# "rh.apps.RhConfig",
# "metrologia.apps.MetrologiaConfig",
# ... etc ...

# Módulo legado (compatibilidade)
"qms",
```

## Resolution Path

### Option 1: Complete the Modularization (Recommended)
1. Move all models from `qms/models.py` to their respective module apps
2. Create migrations for each module
3. Run data migrations to consolidate databases
4. Update all imports across the application
5. Delete the legacy `qms/` module (keep for backward compatibility if needed)

**Timeline:** 2-3 days for complete implementation
**Risk:** High - requires careful database migration

### Option 2: Keep Hybrid Architecture (Current)
1. Keep `qms/` as the source of truth for all models
2. Ensure all new modules import models from qms
3. Keep modular apps for views, forms, utils only
4. Document this pattern clearly

**Timeline:** 0 days - already functional
**Risk:** Low - maintains current working state
**Maintainability:** Medium - confusing structure but working

### Option 3: Rollback to Legacy QMS
1. Remove all modular apps
2. Revert to original `qms/` monolithic structure
3. Keep only legacy documentation

**Timeline:** 1 day
**Risk:** Low - proven working
**Maintainability:** Poor - monolithic nightmare

## Recommended Action

**Choose Option 2 (Hybrid Architecture)** until full modularization can be completed:

1. Update all module imports to use `from qms.models import ...`
2. Keep modular apps for NEW views/forms (don't try to duplicate models)
3. Document the hybrid approach clearly
4. Plan full modularization as Phase 9 (future)

## Testing Strategy

### Current
- Run tests with `INSTALLED_APPS` containing ONLY `"qms"`
- Tests validate qms models, views, forms
- New modular app views/forms tested separately

### For Full Modularization
- Enable each app's INSTALLED_APPS individually
- Run module-specific test suites
- Integration tests for cross-module dependencies

## Code References

**Files with references to both qms and new modules:**
- `config/urls.py` - Imports from both qms and new module apps
- `config/settings.py` - INSTALLED_APPS configuration
- Module `__init__.py` files - Import models from qms or expect local models

## Migration Checklist (For Option 1 Future Implementation)

- [ ] Create data migrations for each module
- [ ] Move models from qms to respective modules
- [ ] Update all import statements across the codebase
- [ ] Create/update URL configurations
- [ ] Create comprehensive integration tests
- [ ] Validation and testing on staging environment
- [ ] Plan database migration for production
- [ ] Deprecation of legacy qms module

---

**Document Status:** Current as of December 8, 2025  
**Next Review:** After Phase 9 completion or when migration decision is made
