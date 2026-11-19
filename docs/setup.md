# Setup Local - CalibraWEB

## Pré-requisitos

- Python 3.11+
- PostgreSQL 14+ (ou SQLite para desenvolvimento)
- Redis 6+
- Git

## Instalação Passo a Passo

### 1. Clonar Repositório

```bash
git clone https://github.com/seu-usuario/CalibraWeb.git
cd CalibraWeb
```

### 2. Criar Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

```bash
# Copiar template
cp .env.example .env

# Editar .env com suas configurações
# Importante: DATABASE_URL, SECRET_KEY, DEBUG
```

### 5. Executar Migrações

```bash
python manage.py migrate
```

### 6. Criar Superuser (Admin)

```bash
python manage.py createsuperuser
```

### 7. Coletar Arquivos Estáticos

```bash
python manage.py collectstatic --noinput
```

### 8. Iniciar Servidor Local

```bash
python manage.py runserver 0.0.0.0:8000
```

Acessar: http://localhost:8000

## Executar Celery Localmente

### Terminal 1: Worker

```bash
celery -A config worker -l info
```

### Terminal 2: Beat (opcional)

```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Terminal 3: Flower (Monitoring)

```bash
celery -A config flower --port=5555
```

Acessar Flower: http://localhost:5555

## Testes

```bash
# Rodar todos os testes
pytest

# Rodar com cobertura
pytest --cov=core --cov=rh --cov=metrologia

# Rodar teste específico
pytest tests/core/test_models.py::test_specific_function
```

## Linting & Formatação

```bash
# Verificar estilo
flake8 . --max-line-length=120

# Formatar código
black . --line-length=120

# Ordenar imports
isort .

# Análise de segurança
bandit -r core rh metrologia
```

## Troubleshooting

### Erro: "No module named 'django'"
```bash
pip install -r requirements.txt
```

### Erro de Banco de Dados
```bash
python manage.py migrate --fake-initial
```

### Redis não conecta
```bash
# Verificar se Redis está rodando
redis-cli ping
```

---

Para mais informações sobre arquitetura, consulte [Arquitetura](./arquitetura.md)

## Migração Neon.tech → Supabase

Cópia fiel do schema `public` (dados, usuários, sessões, permissões). Não exige mudança de código:
o `settings.py` lê `DATABASE_URL` e já exige SSL.

**Pré-requisitos:** `postgresql-client` (`pg_dump`, `pg_restore`, `psql`) com versão >= à do Neon; projeto Supabase
criado com Postgres >= ao do Neon.

**Conexão:** use a URL **direta** do Neon (sem `-pooler`) e, no Supabase, o **Session pooler** (porta 5432).
Nunca o Transaction pooler (6543) — quebra cursores server-side do Django.

```bash
export NEON_URL='postgresql://USER:SENHA@ep-xxx.neon.tech/DB?sslmode=require'
export SUPABASE_HOST='aws-0-sa-east-1.pooler.supabase.com'
export SUPABASE_PORT=5432
export SUPABASE_USER='postgres.<project-ref>'
# a senha do Supabase é pedida pelo script (não vai para arquivos nem para o histórico)

scripts/migrar_neon_supabase.sh preflight   # versões, extensões, nº de tabelas
# --- colocar o app em manutenção (parar escritas) ---
scripts/migrar_neon_supabase.sh all         # dump + restore + sequences + RLS + verify
```

O `verify` compara a contagem de linhas de todas as tabelas e confere as sequences. Só prossiga se terminar com
`VERIFICAÇÃO OK`.

**Troca:**
1. Com `DATABASE_URL` = Session pooler do Supabase (a senha deve ser codificada na URL: `@`→`%40`, `*`→`%2A`, `#`→`%23`):
   `python manage.py showmigrations | grep -v '\[X\]'` deve vir vazio e `python manage.py check` sem erros.
2. Vercel → Settings → Environment Variables: atualizar `DATABASE_URL` (e remover/atualizar `POSTGRES_URL`, `PG*`
   criadas pela integração Neon). Atualizar também worker/beat do Celery, se rodarem fora da Vercel.
3. Redeploy e teste de fumaça (login, auditoria, procedimentos, relatórios).

**Rollback:** voltar `DATABASE_URL` para o Neon (permanece intacto, o script só lê dele). Mantenha-o alguns dias.

**Segurança:** o script habilita RLS em todas as tabelas (sem policies), bloqueando a Data API pública do Supabase;
o Django conecta como `postgres` e não é afetado. Após a migração, redefina a senha do banco se ela foi exposta e
apague o arquivo de dump (`calibraweb_neon.dump`).
