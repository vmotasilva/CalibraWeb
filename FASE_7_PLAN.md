# Phase 7: Templates & Static Files Organization Plan

## Current State
All 29 templates are in `qms/templates/`

## Template Analysis & Mapping

### Shared/Common Templates (Keep in shared or qms)
- `base.html` - Base template used by all
- `registration/login.html` - Login template (Django auth)
- `form_generico.html` - Generic form template (used across modules)
- `import_jobs.html` - Import jobs display

### Metrologia Module Templates (Move to metrologia/templates)
- `modulo_metrologia.html` - Metrologia dashboard
- `detalhe_instrumento.html` - Instrument details
- `registrar_historico_calibracao.html` - Register calibration history
- `visualizar_historico_calibracao.html` - View calibration history
- `preview_certificado.html` - Certificate preview
- `importar_instrumentos.html` - Import instruments
- `importar_historico.html` - Import calibration history
- `importar_categorias.html` - Import instrument categories

### RH Module Templates (Move to rh/templates)
- `modulo_rh.html` - RH dashboard
- `detalhe_colaborador.html` - Employee details
- `editar_colaborador.html` - Edit employee
- `registro_ocorrencia.html` - Record occurrence
- `importar_colaboradores.html` - Import employees
- `importar_ferias.html` - Import vacation data

### Training Module Templates (Move to training/templates)
- `procedimentos_lista.html` - Procedures list
- `procedimentos_form.html` - Procedures form
- `procedimentos_detalhe.html` - Procedures detail
- `procedimentos_base.html` - Procedures base template
- `procedimento_detalhe.html` - Single procedure detail
- `procedimentos_detalhe.html` - Procedures details
- `treinamentos_lista.html` - Training list
- `treinamentos_form.html` - Training form
- `treinamentos_detalhe.html` - Training detail
- `importar_procedimentos.html` - Import procedures

### Shared Templates (GED/Document Management)
- `modulo_ged.html` - GED (Document Management) - Move to shared

### Organization

```
metrologia/templates/metrologia/
├── dashboard.html (renamed from modulo_metrologia.html)
├── instrumento_detalhe.html (renamed from detalhe_instrumento.html)
├── historico_calibracao_form.html (renamed from registrar_historico_calibracao.html)
├── historico_calibracao_detail.html (renamed from visualizar_historico_calibracao.html)
├── certificado_preview.html (renamed from preview_certificado.html)
├── imports/
│   ├── instrumentos.html (from importar_instrumentos.html)
│   ├── historico.html (from importar_historico.html)
│   └── categorias.html (from importar_categorias.html)

rh/templates/rh/
├── dashboard.html (from modulo_rh.html)
├── colaborador_detalhe.html (from detalhe_colaborador.html)
├── colaborador_form.html (from editar_colaborador.html)
├── ocorrencia_form.html (from registro_ocorrencia.html)
├── imports/
│   ├── colaboradores.html (from importar_colaboradores.html)
│   └── ferias.html (from importar_ferias.html)

training/templates/training/
├── dashboard.html (implied, no explicit file)
├── procedimento_lista.html (from procedimentos_lista.html)
├── procedimento_form.html (from procedimentos_form.html)
├── procedimento_detalhe.html (from procedimentos_detalhe.html)
├── procedimento_base.html (from procedimentos_base.html)
├── treinamento_lista.html (from treinamentos_lista.html)
├── treinamento_form.html (from treinamentos_form.html)
├── treinamento_detalhe.html (from treinamentos_detalhe.html)
├── imports/
│   └── procedimentos.html (from importar_procedimentos.html)

shared/templates/shared/
├── dashboard.html (from dashboard.html - main dashboard)
├── ged/
│   └── modulo_ged.html (GED module)
├── imports/
│   └── import_jobs.html (from import_jobs.html)

shared/templates/registration/
├── login.html (from registration/login.html)

shared/templates/
├── base.html (base template used by all)
├── form_generico.html (generic form - used everywhere)
```

## Implementation Strategy

### Phase 7a: Create Directory Structure
1. Create `metrologia/templates/metrologia/`
2. Create `rh/templates/rh/`
3. Create `training/templates/training/`
4. Create `shared/templates/shared/`
5. Create `shared/templates/registration/`
6. Create `shared/templates/` (for base templates)

### Phase 7b: Move Templates
1. Copy templates to appropriate module directories
2. Update template includes/extends in moved templates if needed
3. Test that all views can find their templates

### Phase 7c: Update Template References in Views
1. Update render() calls in views if using explicit paths
2. Test that all templates load correctly

### Phase 7d: Delete Original qms/templates
1. Once confirmed working, delete qms/templates

## Important Notes

- Django's APP_DIRS=True will look for templates in `<app>/templates/` directories
- Templates should be organized as `<app>/templates/<app>/template.html` to avoid name conflicts
- base.html and form_generico.html should remain in shared/ root templates for easy access
- registration/ folder must stay at top-level or in shared for Django auth to find it

## Files to Update

Views that might have hardcoded template paths (unlikely, but check):
- All view render() calls typically use simple names like "dashboard.html"
- Django will find them in the appropriate app's templates folder

## Validation Steps

After moving:
1. [ ] Test each view loads correct template
2. [ ] Verify inheritance/includes work
3. [ ] Check static file loading (base.html CSS/JS)
4. [ ] Confirm no missing templates

---

## Static Files Organization

Current state: Check if there's a `static/` directory

Structure to create:
```
metrologia/static/metrologia/
rh/static/rh/
training/static/training/
procurements/static/procurements/
shared/static/shared/
```
