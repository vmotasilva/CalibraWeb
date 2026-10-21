#!/bin/bash
# Ignored Build Step da Vercel (ignoreCommand em vercel.json).
# Exit 0 = PULA o build/deploy; exit 1 = prossegue com o build.
# Pula quando o commit so altera arquivos que nao afetam a aplicacao em runtime.

# Sem commit anterior disponivel (clone raso) -> faz o build por seguranca.
if ! git rev-parse --verify HEAD^ >/dev/null 2>&1; then
    echo "Sem HEAD^ disponivel: build mantido."
    exit 1
fi

IGNORAVEIS='^(docs/|htmlcov/|PDFs/|Python Files/|\.github/|\.pytest_cache/)|(^|/)tests?/|(^|/)test_[^/]*\.py$|(^|/)tests\.py$|(^|/)conftest\.py$|\.sql$|\.pdf$|^(README|AGENTS|CLAUDE)\.md$|^docs?/.*\.md$|^pytest\.ini$|^requirements-test\.txt$|^\.coveragerc$|^\.pre-commit-config\.yaml$|^\.bandit$'

RELEVANTES=$(git diff --name-only HEAD^ HEAD | grep -v -E "$IGNORAVEIS")

if [ -z "$RELEVANTES" ]; then
    echo "Somente arquivos ignoraveis alterados: build PULADO."
    exit 0
fi

echo "Arquivos relevantes alterados: build mantido."
echo "$RELEVANTES" | head -20
exit 1
