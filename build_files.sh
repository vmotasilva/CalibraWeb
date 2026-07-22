#!/bin/bash
# Install dependencies
python3 -m pip install -r requirements.txt --break-system-packages

# Run migrations (only if database environment variables are set)
if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_URL" ] || [ -n "$PGHOST" ]; then
    echo "==> Database detected. Running migrations..."
    python3 manage.py migrate --noinput
    python3 manage.py setup_module_permissions || true
    python3 manage.py ensure_superuser || true
else
    echo "==> Warning: Database environment variables not detected. Skipping migrations at build time."
fi

# Run collectstatic
echo "==> Running collectstatic..."
python3 manage.py collectstatic --noinput --clear

# Gerar informacoes da versao (Data e Commit Hash)
echo "==> Gerando version_info.json..."
export BUILD_DATE=$(date -d '-3 hours' +'%d/%m/%Y %H:%M')
export SHORT_SHA=${VERCEL_GIT_COMMIT_SHA:0:7}
if [ -z "$SHORT_SHA" ]; then
    SHORT_SHA="local"
fi
echo "{\"hash\": \"$SHORT_SHA\", \"date\": \"$BUILD_DATE\"}" > version_info.json

