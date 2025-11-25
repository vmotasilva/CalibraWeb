Security cleanup recommendations
=================================

I found sensitive artifacts currently present or likely to be present in this repository (e.g. committed virtual environments, database files, certificate PDFs, or hard-coded secrets). To avoid accidentally exposing secrets and personal data, follow these steps.

Quick actions you can run locally (recommended):

1) Add `.gitignore` (already added in this repo) to stop checking in local env, DB and generated files.

2) Remove files from the index (keeps them locally but removes in git history):

   # Windows PowerShell
   git rm --cached -r venv
   git rm --cached db.sqlite3
   git rm --cached -r certificados
   git commit -m "chore: remove sensitive files from git index and add .gitignore"

3) Rewrite git history to purge sensitive files from all commits (optional but strongly recommended):

   - Using BFG Repo Cleaner (easier):
     - Install BFG (https://rtyley.github.io/bfg-repo-cleaner/)
     - Example: bfg --delete-folders '{venv,certificados}' --delete-files db.sqlite3 --no-blob-protection
     - Then follow with: git reflog expire --expire=now --all && git gc --prune=now --aggressive

   - Using git filter-repo (recommended over git-filter-branch):
     - pip install git-filter-repo
     - Example: git filter-repo --invert-paths --paths venv --paths db.sqlite3 --paths certificados

4) Rotate secrets / credentials after purge:
   - If SECRET_KEY, admin passwords, API keys or other secrets were committed earlier, rotate them in your services immediately.

5) Keep sensitive files out of repo going forward — use artifact storage or secure object storage (S3), or `django-storages` for uploaded files.

If you want, I can perform safe removals of files here in the repo (git rm and commit), and add a history-cleaning script — tell me to proceed and I will continue with the next steps in the plan.
