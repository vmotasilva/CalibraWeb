# Banco de dados do Preview (Vercel)

## Situação
Os ambientes **Preview** e **Production** da Vercel têm cada um o seu `DATABASE_URL`, mas, na prática,
o preview usava o mesmo banco da produção: um build de preview aplicou migrações que depois
apareceram como já aplicadas no build de produção (`No migrations to apply`).
O banco de `DATABASE_URL` **não é** o da integração Neon (`STORAGE_*`): no log do build, o diagnóstico
`[db-guard]` mostra impressões digitais diferentes para os dois.

Consequência: um preview lê e grava dados reais e, sem proteção, o build de qualquer branch migrava
a produção.

## Proteção no build (`build_files.sh`)
Em build de **preview**, o build **não** roda `migrate`, `setup_module_permissions` nem
`ensure_superuser`, a menos que `PREVIEW_DB_PROPRIO=1` esteja definido. O ambiente vem de
`VERCEL_ENV` (ou, se faltar, da branch). Builds de produção não mudam.
O script `scripts/db_compartilhado_com_producao.py` só imprime um diagnóstico sem segredos
(impressões digitais curtas de host/banco) para facilitar a conferência.

Efeito colateral: enquanto o preview usar o banco da produção, telas que dependem de tabelas ou
colunas novas da branch podem dar erro 500 no preview (as migrações não rodam lá). Por isso o
preview de uma branch com migração **não serve** para testar essa funcionalidade.

## Separar de verdade: banco próprio para o Preview (uma vez)
1. Crie um banco novo para o Preview, a partir de uma cópia da produção (por exemplo, uma *branch*
   no Neon ou um projeto separado no provedor que a produção usa hoje).
2. Na **Vercel → Settings → Environment Variables**, edite `DATABASE_URL` **somente do ambiente
   Preview** com a string de conexão desse banco. Não altere o `DATABASE_URL` de Production.
3. Ainda no ambiente **Preview**, crie `PREVIEW_DB_PROPRIO` = `1`.
4. Faça um novo deploy de preview. No log do build, as migrações devem ser aplicadas e o aviso de
   "PULADOS" não deve aparecer.
5. Para renovar os dados do preview, recrie/reponha o banco a partir da produção.

Atenção: só defina `PREVIEW_DB_PROPRIO=1` depois de ter certeza de que o `DATABASE_URL` do Preview
**não** é o da produção.
