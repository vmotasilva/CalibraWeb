## Summary

Allow multiple dated training records for the same procedure.

This PR includes:
- Model change: `RegistroTreinamento.unique_together` now includes `data_treinamento`.
- Migration: `procedures/migrations/0030_allow_multiple_procedimento_dates.py`.
- Importer logic: duplicate detection and update/create now consider date for procedimento entries.
- Tests: unit and integration tests covering the importer and the Histórico view; end-to-end upload test auto-skips if two-factor is enforced in the environment.
- UI: small explanatory note added to the Histórico page.
- CHANGELOG entry and a DEPLOYMENT.md checklist.

## Migration notes
- **IMPORTANT:** run `python manage.py migrate` in **staging** before production and validate imports and the Histórico page.

## Testing checklist
- [ ] All unit tests pass (CI will run full test-suite on PR).
- [ ] Run importer manually in staging with an XLSX containing two rows for the same collaborator & procedure with different dates (should create two registros).
- [ ] Validate Histórico page shows both dates and status badges as expected.

## Rollback plan
- If migration causes issues, revert the PR and re-run migrations to previous state (restore DB from backup if necessary).

## Reviewer notes
- Focus on `procedures/views/lista_presenca_views.py` (duplicate key & update_or_create changes) and `procedures/models.py` (unique_together change + migration).
- The end-to-end upload test is intentionally resilient to 2FA-enabled environments to avoid CI flakiness.

Thank you! 🎯
