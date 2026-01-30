Deployment checklist — feature/allow-multiple-procedure-dates

1. Merge the branch `feature/allow-multiple-procedure-dates` into `main` via PR after review.
2. On staging:
   - Pull latest `main` and run `python manage.py migrate` to apply `procedures.0030_allow_multiple_procedimento_dates`.
   - Run `python manage.py test` (or your CI pipeline) to ensure all tests pass including the new importer tests.
   - Perform basic smoke tests: import a small XLSX with multiple dated records for same procedure and validate the Histórico page shows all records.
3. When staging is green, schedule a production deploy (preferably during a maintenance window):
   - Backup production DB.
   - Run `python manage.py migrate` in production.
   - Run a quick smoke test in production.
4. Post-deploy:
   - Announce change to the team: new behaviour is that the system accepts multiple registros for same (colaborador, procedimento) when dates differ.
   - Monitor error logs for any migration-related issues for the next 24–48 hours.

Notes:
- The migration only relaxes uniqueness to include date; it does not back-fill or alter existing `RegistroTreinamento` rows.
- If you want a one-time audit (e.g., find procedures with multiple identical records), I can provide an ad-hoc script.
