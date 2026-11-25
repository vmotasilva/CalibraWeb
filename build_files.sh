#!/bin/bash
# Install dependencies
python3 -m pip install -r requirements.txt --break-system-packages

# Preview que aponta para o banco de PRODUCAO nao pode alterar esse banco no build
# (migrate, permissoes e superusuario). Use um banco proprio no Preview para migrar la.
# Ambiente: VERCEL_ENV; se a Vercel nao expuser, deduz pela branch (VERCEL_GIT_COMMIT_REF).
AMBIENTE="${VERCEL_ENV:-${VERCEL_TARGET_ENV:-}}"
if [ -z "$AMBIENTE" ] && [ -n "$VERCEL_GIT_COMMIT_REF" ]; then
    if [ "$VERCEL_GIT_COMMIT_REF" = "main" ]; then AMBIENTE="production"; else AMBIENTE="preview"; fi
fi
echo "==> [db-guard] ambiente do build: ${AMBIENTE:-desconhecido}"
PULAR_BANCO=0
python3 scripts/db_compartilhado_com_producao.py
GUARD_RC=$?
if [ "$AMBIENTE" = "preview" ] && [ $GUARD_RC -eq 0 ]; then
    PULAR_BANCO=1
    echo "==> AVISO: este preview usa o MESMO banco da producao. Migracoes, permissoes e superusuario foram PULADOS."
    echo "==>        Configure um banco proprio em DATABASE_URL (ambiente Preview) para testar migracoes. Ver docs/DEPLOY_BANCO_PREVIEW.md"
elif [ -z "$AMBIENTE" ] && [ $GUARD_RC -eq 0 ]; then
    echo "==> AVISO: nao foi possivel identificar o ambiente do build; o banco coincide com o da producao e as migracoes seguem normalmente."
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
