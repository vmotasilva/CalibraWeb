# Banco de dados do Preview (Vercel)

## Situação
O ambiente **Preview** da Vercel usa o mesmo banco Neon da produção (`DATABASE_URL` do Preview é uma
cópia de `STORAGE_DATABASE_URL`). Consequências: um preview lê e grava dados reais e, antes da
proteção abaixo, o build de qualquer branch aplicava as suas migrações na produção.

## Proteção no build (`build_files.sh`)
Em build de preview cujo banco é o da produção, o build **não** roda `migrate`,
`setup_module_permissions` nem `ensure_superuser`; ele só avisa no log
(`AVISO: este preview usa o MESMO banco da producao`). A comparação é feita por
`scripts/db_compartilhado_com_producao.py` (host sem `-pooler` + nome do banco; nada é impresso).
Builds de produção não mudam.

Efeito colateral: enquanto o preview usar o banco da produção, telas que dependem de tabelas ou
colunas novas da branch podem dar erro 500 no preview (as migrações ainda não existem lá).
A solução é o banco próprio abaixo.

## Separar de verdade: banco próprio para o Preview (uma vez)
1. No **Neon Console** do projeto, abra *Branches* e crie a branch `preview` a partir da principal
   (cópia instantânea dos dados, sem custo de duplicar o banco).
2. Copie a *connection string* da branch `preview` (a "pooled").
3. Na **Vercel → Settings → Environment Variables**, edite `DATABASE_URL` **somente do ambiente
   Preview** e troque o valor por essa string. Não altere o `DATABASE_URL` de Production.
4. Faça um novo deploy de preview. No log do build devem aparecer as migrações sendo aplicadas
   (e não mais o aviso de banco compartilhado).
5. Para renovar os dados do preview: no Neon, *Reset from parent* na branch `preview`.

Os `STORAGE_*` (integração Neon) continuam apontando para a produção; o app lê `DATABASE_URL` primeiro.
Não use essas variáveis no Preview.
