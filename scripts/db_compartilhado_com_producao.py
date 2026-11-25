#!/usr/bin/env python3
"""Diz se o banco configurado neste build e o mesmo da producao (integracao Neon).

Uso (no build da Vercel):  python3 scripts/db_compartilhado_com_producao.py
Saida 0 = o banco ATUAL e o da producao (compartilhado); 1 = e um banco diferente;
2 = nao foi possivel comparar (sem URL de banco).

Compara host (sem o sufixo "-pooler") e nome do banco, ignorando usuario e senha.
Nenhuma URL e impressa (so impressoes digitais curtas), para nao vazar segredos nos logs.
"""
import os
import sys
from urllib.parse import urlparse

# Variaveis da integracao Neon, iguais em todos os ambientes da Vercel.
VARS_PRODUCAO = (
    "STORAGE_DATABASE_URL",
    "STORAGE_DATABASE_URL_UNPOOLED",
    "STORAGE_POSTGRES_URL",
    "STORAGE_POSTGRES_URL_NON_POOLING",
    "STORAGE_POSTGRES_PRISMA_URL",
)
VARS_ATUAIS = ("DATABASE_URL", "POSTGRES_URL", "POSTGRESQL_URL")


def identidade(url):
    """(host sem -pooler, banco) ou None."""
    try:
        p = urlparse(url.strip())
    except Exception:
        return None
    host = (p.hostname or "").lower().replace("-pooler", "")
    banco = (p.path or "").lstrip("/").split("?")[0]
    return (host, banco) if host and banco else None


def _marca(valor):
    """Impressão digital curta (não reversível) só para comparar nos logs; nunca a URL."""
    import hashlib

    return hashlib.sha256(str(valor).encode()).hexdigest()[:6]


def diagnostico(env=os.environ):
    """Linha de log sem segredos: quais variáveis existem e se host/banco coincidem."""
    atual_var = next((v for v in VARS_ATUAIS if env.get(v)), None)
    atual = identidade(env[atual_var]) if atual_var else None
    prod = {v: identidade(env[v]) for v in VARS_PRODUCAO if env.get(v)}
    partes = [
        f"atual={atual_var or 'ausente'}",
        f"host#{_marca(atual[0]) if atual else '-'}",
        f"db#{_marca(atual[1]) if atual else '-'}",
    ]
    for nome, ident in prod.items():
        partes.append(f"{nome}=host#{_marca(ident[0]) if ident else '-'}/db#{_marca(ident[1]) if ident else '-'}")
    if not prod:
        partes.append("STORAGE_*=ausentes")
    return " ".join(partes)


def main(env=os.environ):
    atual = next((env[v] for v in VARS_ATUAIS if env.get(v)), None)
    if not atual:
        return 2
    ident = identidade(atual)
    if ident is None:
        return 2
    producao = {identidade(env[v]) for v in VARS_PRODUCAO if env.get(v)} - {None}
    return 0 if ident in producao else 1


if __name__ == "__main__":
    print("[db-guard]", diagnostico())
    sys.exit(main())
