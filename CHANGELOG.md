# Changelog

## 2026-01-30 — Allow multiple dated training records for same procedure
- Fix: Importer and model updated to allow multiple `RegistroTreinamento` entries for the same (colaborador, procedimento) when `data_treinamento` differs. This prevents accidental overwrites of historical trainings during imports.
- Migration: `procedures/migrations/0030_allow_multiple_procedimento_dates.py` adds the new unique constraint `(colaborador, procedimento, data_treinamento)`.
- Tests: Added unit and integration tests covering multiple dated imports and the histórico page display; the end-to-end upload test auto-skips in environments with 2FA.
- UI: Small explanatory note added to the Histórico de Treinamentos page clarifying it shows all dated registros.

Notes:
- Apply the migration in staging/CI before deploying to production.
- Recommended: run the full test suite on CI with 2FA disabled or configure the integration test to run in non-2FA environments.
