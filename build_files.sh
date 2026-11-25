#!/bin/bash
# Install dependencies
python3 -m pip install -r requirements.txt --break-system-packages

# Build de PREVIEW nunca altera o banco (migrate, permissoes e superusuario), porque nao ha como saber, de
# dentro do preview, se o DATABASE_URL dele e o da producao (ja aconteceu: um preview migrou o banco de
# producao). Para migrar em preview, crie um banco proprio, configure o DATABASE_URL do ambiente Preview
# e defina PREVIEW_DB_PROPRIO=1 (ver docs/DEPLOY_BANCO_PREVIEW.md).
# Ambiente: VERCEL_ENV; se a Vercel nao expuser, deduz pela branch (VERCEL_GIT_COMMIT_REF).
AMBIENTE="${VERCEL_ENV:-${VERCEL_TARGET_ENV:-}}"
if [ -z "$AMBIENTE" ] && [ -n "$VERCEL_GIT_COMMIT_REF" ]; then
    if [ "$VERCEL_GIT_COMMIT_REF" = "main" ]; then AMBIENTE="production"; else AMBIENTE="preview"; fi
fi
echo "==> [db-guard] ambiente do build: ${AMBIENTE:-desconhecido}"
python3 scripts/db_compartilhado_com_producao.py || true   # so diagnostico (sem segredos)
PULAR_BANCO=0
if [ "$AMBIENTE" = "preview" ] && [ "${PREVIEW_DB_PROPRIO:-0}" != "1" ]; then
    PULAR_BANCO=1
    echo "==> AVISO: build de PREVIEW sem PREVIEW_DB_PROPRIO=1: migracoes, permissoes e superusuario foram PULADOS para nao alterar o banco de producao."
    echo "==>        Para migrar em preview, use um banco proprio. Ver docs/DEPLOY_BANCO_PREVIEW.md"
fi

# Run migrations (only if database environment variables are set)
if [ "$PULAR_BANCO" = "1" ]; then
    echo "==> Build de preview sobre o banco de producao: sem acesso de escrita ao banco neste passo."
elif [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_URL" ] || [ -n "$PGHOST" ]; then
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

# Sincronizar Changelog
echo "==> Sincronizando changelog..."
python3 manage.py shell -c "from shared.changelog_sync import sync_changelog; sync_changelog()"
