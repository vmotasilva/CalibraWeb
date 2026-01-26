# 🚂 Deploy CalibraWeb no Railway - Setup Completo

## ✅ Pré-requisitos
- Conta Railway (grátis): https://railway.app
- Repositório GitHub conectado
- Todos os arquivos já estão configurados!

## 🚀 Deploy em 5 Passos

### Passo 1: Criar Projeto Railway

1. Acesse https://railway.app/new
2. Clique em **"Deploy from GitHub repo"**
3. Autorize Railway a acessar seus repositórios
4. Selecione **"CalibraWeb"**

### Passo 2: Adicionar PostgreSQL

1. No projeto, clique **"+ New"**
2. Selecione **"Database"** → **"Add PostgreSQL"**
3. Railway criará automaticamente e injetará `DATABASE_URL`

### Passo 3: Adicionar Redis (Opcional - para Celery)

1. Clique **"+ New"** novamente
2. Selecione **"Database"** → **"Add Redis"**
3. Railway injetará `REDIS_URL` automaticamente

### Passo 4: Configurar Variáveis de Ambiente

No serviço **"CalibraWeb"**, vá em **"Variables"** e adicione:

```bash
# OBRIGATÓRIAS
SECRET_KEY=9XQa6MuCN4COJ79b7x5llFBZ9i0xVIR_ckezSvXkwOpWuU7AdciIxJOExdTLBkblDMk
ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}},.railway.app
CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}},https://*.railway.app

# OPCIONAIS (já tem defaults)
DEBUG=False
TIME_ZONE=America/Sao_Paulo
DJANGO_SETTINGS_MODULE=config.settings
```

**Nota:** `DATABASE_URL`, `REDIS_URL` e `PORT` são injetados automaticamente pelo Railway!

### Passo 5: Fazer Deploy

1. Railway detecta push e inicia deploy automaticamente
2. Ou clique **"Deploy"** manualmente
3. Aguarde 3-5 minutos

## 🔍 Verificar Deploy

### Health Check
```bash
curl https://seu-app.up.railway.app/healthz/
# Esperado: {"status":"ok","service":"CalibraWeb"}
```

### Ver Logs
No Railway Dashboard:
- Clique no serviço **"CalibraWeb"**
- Vá para aba **"Deployments"**
- Clique no deploy ativo
- Veja logs em tempo real

Procure por:
```
==> Checking database connection...
==> Running database migrations...
==> Collecting static files...
==> Starting Gunicorn server...
[INFO] Listening at: http://0.0.0.0:XXXX
```

## 👤 Criar Superusuário

### Opção A: Via Railway Shell (Recomendado)
1. No serviço, clique nos **"..."** (três pontos)
2. Selecione **"Shell"**
3. Execute:
```bash
python manage.py createsuperuser
```

### Opção B: Com Variáveis de Ambiente
1. Adicione nas variáveis:
```bash
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=SuaSenhaSegura123!
```

2. No Shell:
```bash
python manage.py ensure_superuser
```

## 📊 Comandos Úteis (via Shell)

```bash
# Ver status do banco
python manage.py check --database default

# Importar dados
python manage.py shell < scripts/importar_procedimentos.py

# Sincronizar treinamentos
python manage.py rebuild_treinamentos
python manage.py cleanup_treinamentos
python manage.py sync_treinamentos

# Ver versão Python
python --version

# Listar migrations aplicadas
python manage.py showmigrations
```

## 🔄 Atualizar Aplicação

```bash
# Local
git add .
git commit -m "Sua mensagem"
git push origin main
```

Railway detecta e redeploya automaticamente em 2-3 minutos! 🎉

## 🐛 Troubleshooting

### Erro 502 Bad Gateway
**Causa:** Container não iniciou ou porta incorreta

**Solução:**
1. Verificar logs para erros
2. Confirmar `SECRET_KEY` está definida
3. Verificar `PORT` está sendo usado: `${PORT:-8000}`

### Erro: ImproperlyConfigured
**Causa:** Variável de ambiente faltando

**Solução:**
1. Verificar `SECRET_KEY` nas variáveis
2. Verificar `ALLOWED_HOSTS` inclui domínio Railway
3. Redeploy após adicionar variáveis

### Erro: relation "auth_user" does not exist
**Causa:** Migrations não rodaram

**Solução:**
1. Verificar logs do deploy - deve mostrar "Running database migrations"
2. Forçar migrations via Shell:
```bash
python manage.py migrate --noinput
```

### Static Files 404
**Causa:** collectstatic falhou

**Solução:**
```bash
python manage.py collectstatic --noinput --clear
```

### Database Connection Error
**Causa:** PostgreSQL não conectado

**Solução:**
1. Verificar service PostgreSQL está "Active"
2. `DATABASE_URL` deve estar nas variáveis do web service
3. Testar conexão:
```bash
python manage.py check --database default
```

## 📈 Monitoramento

### Métricas Disponíveis
- CPU Usage
- Memory Usage
- Request Count
- Response Times
- Deployments History

### Logs Estruturados
Railway mostra logs por:
- Build (instalação dependências)
- Deploy (migrations, collectstatic)
- Runtime (Gunicorn, aplicação)

### Alertas
Configure no Railway:
- Downtime alerts (email)
- Deploy failures
- Resource limits

## 💰 Custos Railway

**Plano Gratuito:**
- $5 crédito mensal
- Suficiente para 1 app + PostgreSQL pequeno
- ~500h runtime/mês

**Plano Hobby ($5/mês):**
- $5 crédito + $5 uso adicional
- Melhor performance
- Priority support

**Plano Pro ($20/mês):**
- Recursos ilimitados
- Teams
- Advanced features

## ✅ Checklist Pós-Deploy

- [ ] Health endpoint responde 200: `/healthz/`
- [ ] Admin acessível: `/admin/`
- [ ] Superusuário criado
- [ ] Login funciona
- [ ] Static files carregando (CSS/JS)
- [ ] Database migrations aplicadas
- [ ] Dados iniciais importados
- [ ] Treinamentos sincronizados
- [ ] Logs sem erros críticos

## 🔐 Segurança

✅ **Já configurado em produção** (quando `DEBUG=False`):
- HTTPS forçado (Railway gerencia SSL)
- Cookies seguros
- HSTS habilitado
- XSS protection
- CSRF protection
- Content type sniffing bloqueado

## 📚 Recursos

- **Railway Docs:** https://docs.railway.app
- **Railway Discord:** Suporte da comunidade
- **Status Page:** https://status.railway.app
- **Changelog:** https://railway.app/changelog

---

## 🎯 Resumo Rápido

```bash
# 1. Criar projeto: railway.app/new
# 2. Adicionar PostgreSQL
# 3. Adicionar variáveis (SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS)
# 4. Deploy automático
# 5. Criar superusuário via Shell
# 6. Acessar: https://seu-app.up.railway.app
```

**Tempo total:** ~5-10 minutos ⚡

**Vantagens sobre Render:**
- ✅ 3x mais rápido (deploys 2-3 min vs 8-12 min)
- ✅ Sem sleep (sempre ativo no free tier)
- ✅ Melhor cache de builds
- ✅ Logs mais claros
- ✅ Shell interativo melhor
