# Deploy CalibraWeb no Railway - Guia Completo

## 📋 Pré-requisitos

- Conta Railway ativa
- Repositório Git configurado
- Variáveis de ambiente preparadas

## 🔧 Configuração de Variáveis de Ambiente

No Railway, configure as seguintes variáveis:

```bash
SECRET_KEY=<sua-chave-gerada-securely>
ALLOWED_HOSTS=your-app.up.railway.app,your-custom-domain.com
DATABASE_URL=<fornecido-automaticamente-pelo-railway-postgres>
CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app,https://your-custom-domain.com
DEBUG=False
TIME_ZONE=America/Sao_Paulo
CELERY_BROKER_URL=<redis-url-se-usar-celery>
```

### Gerar SECRET_KEY

```python
# Local
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

## 🚀 Processo de Deploy

### 1. Criar Novo Projeto Railway

```bash
# Via Railway CLI (opcional)
railway login
railway init
railway link
```

Ou use o dashboard web para conectar seu repositório GitHub.

### 2. Adicionar PostgreSQL

No Railway Dashboard:
1. Click "+ New"
2. Selecione "Database" → "PostgreSQL"
3. `DATABASE_URL` será injetado automaticamente

### 3. Adicionar Redis (se usar Celery)

1. Click "+ New"
2. Selecione "Database" → "Redis"
3. Copie a URL para `CELERY_BROKER_URL`

### 4. Deploy da Aplicação

Railway detecta automaticamente:
- `Dockerfile` → build da imagem
- `Procfile` → comandos de inicialização

**Processos configurados:**
- `web`: Gunicorn server (porta dinâmica via `$PORT`)
- `worker`: Celery worker (opcional)
- `beat`: Celery beat scheduler (opcional)

## 🔍 Verificação de Saúde

Teste o health endpoint após deploy:

```bash
curl https://your-app.up.railway.app/healthz/
# Esperado: {"status": "ok", "service": "CalibraWeb"}
```

## 🗄️ Gerenciamento de Banco de Dados

### Primeira Vez (Novo DB)

```bash
# Via Railway CLI
railway run python manage.py migrate
railway run python manage.py createsuperuser
railway run python manage.py collectstatic --noinput
```

### Resetar Banco (Solução para Corrupção)

**Opção 1: Recriar serviço PostgreSQL no Railway**
1. Delete o serviço PostgreSQL existente
2. Crie um novo (gera novo `DATABASE_URL`)
3. Execute migrations

**Opção 2: Via psql (requer acesso direto)**
```sql
DROP DATABASE railway;
CREATE DATABASE railway;
```

### Importar Dados

```bash
# Procedimentos
railway run python manage.py shell < scripts/importar_procedimentos.py

# Colaboradores, instrumentos, etc.
railway run python manage.py imp_colab_view
# ou via admin web após deploy
```

## 🛠️ Comandos de Manutenção de Treinamentos

Após mudanças no modelo de treinamentos ou import de dados:

```bash
# Recria registros de treinamento a partir dos pacotes
railway run python manage.py rebuild_treinamentos

# Remove registros órfãos ou de procedimentos sem aplica_treinamento
railway run python manage.py cleanup_treinamentos

# Sincroniza revisões (dry-run primeiro)
railway run python manage.py sync_treinamentos --dry-run
railway run python manage.py sync_treinamentos
```

## 🐛 Troubleshooting 502 Bad Gateway

### Causas Comuns

1. **SECRET_KEY não configurado**
   - Erro: `ImproperlyConfigured: SECRET_KEY is required`
   - Solução: Adicione variável no Railway

2. **Porta incorreta**
   - Railway fornece `$PORT` dinamicamente
   - Verificar: Dockerfile/Procfile usam `${PORT:-8000}`

3. **Database inacessível**
   - Verifique se PostgreSQL está running
   - Teste conexão: `railway run python manage.py check --database default`

4. **Timeout de inicialização**
   - Gunicorn configurado com `--timeout 120`
   - Migrations longas podem exceder; execute separadamente

5. **Collectstatic falhando**
   - Movido para runtime (não build)
   - Execute manualmente se necessário

### Logs

```bash
# Railway CLI
railway logs

# Filtrar por serviço
railway logs --service web
railway logs --service worker
```

### Verificações

```bash
# Django health
railway run python manage.py check --deploy

# Test database
railway run python manage.py migrate --check

# Shell interativo
railway run python manage.py shell
```

## 📊 Monitoramento

- **Health endpoint**: `/healthz/` (retorna 200 OK quando saudável)
- **Admin**: `/admin/` (requer autenticação)
- **Logs**: Dashboard Railway ou CLI

## 🔐 Segurança

Configurações de produção ativadas automaticamente quando `DEBUG=False`:

- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000`
- `SECURE_SSL_REDIRECT = False` (Railway gerencia SSL)
- `X_FRAME_OPTIONS = DENY`

## 🔄 Atualização de Código

```bash
# Push para branch principal
git push origin main

# Railway auto-deploya se integração GitHub ativa
# Ou force rebuild via dashboard
```

## 📝 Checklist de Deploy

- [ ] Variáveis de ambiente configuradas
- [ ] PostgreSQL adicionado e conectado
- [ ] SECRET_KEY gerado e definido
- [ ] ALLOWED_HOSTS inclui domínio Railway
- [ ] Migrations executadas
- [ ] Superusuário criado
- [ ] Health endpoint respondendo 200
- [ ] Admin acessível
- [ ] Collectstatic executado
- [ ] Dados iniciais importados
- [ ] Treinamentos sincronizados

## 🆘 Suporte

Se problemas persistirem:

1. Verifique logs Railway
2. Confirme todas variáveis de ambiente
3. Teste localmente com configuração similar
4. Revise migrations pendentes
5. Verifique integridade do banco de dados

---

**Última atualização:** 2025-11-26  
**Versão Django:** 5.2  
**Python:** 3.12
