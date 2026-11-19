#!/usr/bin/env bash
# Migra o banco do CalibraWeb do Neon.tech para o Supabase (cópia fiel do schema public).
#
# Uso:
#   export NEON_URL='postgresql://USER:SENHA@ep-xxx.REGIAO.aws.neon.tech/DB?sslmode=require'   # URL DIRETA (sem "-pooler")
#   export SUPABASE_HOST='aws-0-sa-east-1.pooler.supabase.com'   # host do Session pooler (ou db.<ref>.supabase.co)
#   export SUPABASE_PORT='5432'
#   export SUPABASE_USER='postgres.<project-ref>'                # no pooler; 'postgres' na conexão direta
#   export SUPABASE_DB='postgres'
#   # A senha do Supabase NÃO vai em variável de ambiente persistente: o script pergunta (sem eco).
#   # Opcional: SUPABASE_PASSWORD (apenas para a sessão atual).
#
#   scripts/migrar_neon_supabase.sh preflight   # versões + contagem de linhas do Neon
#   scripts/migrar_neon_supabase.sh dump        # gera dump local
#   scripts/migrar_neon_supabase.sh restore     # restaura no Supabase + sequences + RLS
#   scripts/migrar_neon_supabase.sh verify      # compara contagens Neon x Supabase
#   scripts/migrar_neon_supabase.sh all         # dump + restore + verify
#
# Nada aqui altera o Neon (somente leitura). Rollback = voltar DATABASE_URL para o Neon.
set -euo pipefail

DUMP_FILE="${DUMP_FILE:-./calibraweb_neon.dump}"
SCHEMA="${SCHEMA:-public}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "ERRO: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' não encontrado (instale o postgresql-client)."; }

need psql; need pg_dump; need pg_restore

[ -n "${NEON_URL:-}" ] || die "defina NEON_URL (URL direta do Neon)."
case "$NEON_URL" in *-pooler*) die "NEON_URL aponta para o pooler. Use a URL direta (sem '-pooler') para o pg_dump.";; esac

sb_env() {
  : "${SUPABASE_HOST:?defina SUPABASE_HOST}"
  : "${SUPABASE_USER:?defina SUPABASE_USER}"
  SUPABASE_PORT="${SUPABASE_PORT:-5432}"
  SUPABASE_DB="${SUPABASE_DB:-postgres}"
  if [ "$SUPABASE_PORT" = "6543" ]; then
    echo "AVISO: porta 6543 = Transaction pooler. Para migração use 5432 (Session pooler/direta)." >&2
    die "restore/verify exigem sessão. Use a porta 5432."
  fi
  if [ -z "${SUPABASE_PASSWORD:-}" ]; then
    read -r -s -p "Senha do Supabase: " SUPABASE_PASSWORD; echo
  fi
  export PGPASSWORD="$SUPABASE_PASSWORD" PGSSLMODE="${SUPABASE_SSLMODE:-require}"
}

# Executa psql no Supabase (credenciais via variáveis libpq, sem URL => caracteres especiais ok)
sb_psql() { PGPASSWORD="$SUPABASE_PASSWORD" PGSSLMODE="${SUPABASE_SSLMODE:-require}" psql -h "$SUPABASE_HOST" -p "$SUPABASE_PORT" -U "$SUPABASE_USER" -d "$SUPABASE_DB" -v ON_ERROR_STOP=1 "$@"; }
neon_psql() { psql "$NEON_URL" -v ON_ERROR_STOP=1 "$@"; }

tables_of() { # $1 = neon|sb
  local q="select table_name from information_schema.tables where table_schema='${SCHEMA}' and table_type='BASE TABLE' order by 1"
  if [ "$1" = neon ]; then neon_psql -At -c "$q"; else sb_psql -At -c "$q"; fi
}

count_rows() { # $1 = neon|sb ; $2 = tabela
  local q="select count(*) from \"${SCHEMA}\".\"$2\""
  if [ "$1" = neon ]; then neon_psql -At -c "$q"; else sb_psql -At -c "$q"; fi
}

cmd_preflight() {
  echo "==> Versão do Postgres (Neon):"
  neon_psql -At -c "show server_version"
  echo "==> Extensões instaladas no Neon (informativo):"
  neon_psql -At -c "select extname from pg_extension order by 1" | sed 's/^/   - /'
  echo "==> Tabelas em ${SCHEMA}: $(tables_of neon | wc -l)"
  if [ -n "${SUPABASE_HOST:-}" ]; then
    sb_env
    echo "==> Versão do Postgres (Supabase):"
    sb_psql -At -c "show server_version"
    echo "   (a versão do Supabase deve ser >= à do Neon)"
  fi
}

cmd_dump() {
  echo "==> Gerando dump do Neon (schema ${SCHEMA}) em ${DUMP_FILE}"
  umask 077
  pg_dump "$NEON_URL" --format=custom --schema="$SCHEMA" \
    --no-owner --no-privileges --no-acl --file="$DUMP_FILE"
  echo "==> Dump pronto: $(du -h "$DUMP_FILE" | cut -f1). Guarde-o: contém TODOS os dados (não versionar)."
}

cmd_restore() {
  [ -f "$DUMP_FILE" ] || die "dump não encontrado: $DUMP_FILE (rode 'dump' antes)."
  sb_env
  echo "==> Destino: ${SUPABASE_USER}@${SUPABASE_HOST}:${SUPABASE_PORT}/${SUPABASE_DB}"
  existing="$(sb_psql -At -c "select count(*) from information_schema.tables where table_schema='${SCHEMA}' and table_type='BASE TABLE'")"
  if [ "$existing" -gt 0 ] && [ "${FORCE:-0}" != "1" ]; then
    die "o Supabase já tem ${existing} tabela(s) em ${SCHEMA}. Para sobrescrever, rode com FORCE=1."
  fi

  echo "==> Restaurando (pode levar alguns minutos)..."
  PGPASSWORD="$SUPABASE_PASSWORD" PGSSLMODE="${SUPABASE_SSLMODE:-require}" pg_restore \
    -h "$SUPABASE_HOST" -p "$SUPABASE_PORT" -U "$SUPABASE_USER" -d "$SUPABASE_DB" \
    --schema="$SCHEMA" --no-owner --no-privileges --no-acl --clean --if-exists \
    --exit-on-error "$DUMP_FILE"

  echo "==> Ajustando sequences (IDs auto-incrementais)..."
  sb_psql -q -f "$HERE/ajustar_sequences.sql"

  echo "==> Habilitando RLS nas tabelas (bloqueia a Data API pública; Django não é afetado)..."
  sb_psql -q -f "$HERE/rls_supabase.sql"

  echo "==> ANALYZE..."
  sb_psql -q -c "analyze"
  echo "==> Restore concluído. Rode: $0 verify"
}

cmd_verify() {
  sb_env
  local ok=1 n_tables=0
  printf "%-60s %12s %12s  %s\n" TABELA NEON SUPABASE STATUS
  while IFS= read -r t; do
    [ -n "$t" ] || continue
    n_tables=$((n_tables+1))
    a="$(count_rows neon "$t")"
    b="$(count_rows sb "$t" 2>/dev/null || echo AUSENTE)"
    if [ "$a" = "$b" ]; then s="ok"; else s="DIVERGE"; ok=0; fi
    printf "%-60s %12s %12s  %s\n" "$t" "$a" "$b" "$s"
  done < <(tables_of neon)
  echo "----"
  echo "Tabelas comparadas: $n_tables"

  echo "==> Sequences abaixo do MAX(id):"
  seq_out="$(sb_psql -At -f "$HERE/checar_sequences.sql" 2>&1 | grep SEQ_PROBLEMA || true)"
  if [ -n "$seq_out" ]; then echo "$seq_out"; ok=0; else echo "   nenhuma"; fi

  if [ "$ok" = 1 ]; then
    echo "VERIFICAÇÃO OK: contagens idênticas e sequences consistentes."
    echo "Próximos passos: DATABASE_URL=<Session pooler> -> python manage.py showmigrations | grep -v '\[X\]'  (deve ser vazio)"
  else
    echo "VERIFICAÇÃO FALHOU: não troque a DATABASE_URL de produção." >&2
    exit 2
  fi
}

case "${1:-}" in
  preflight) cmd_preflight ;;
  dump)      cmd_dump ;;
  restore)   cmd_restore ;;
  verify)    cmd_verify ;;
  all)       cmd_dump; cmd_restore; cmd_verify ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
