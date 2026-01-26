# RAILWAY DEPLOYMENT GUIDE - CALIBRAWEB
## Passo-a-Passo Completo para Deploy em Produção

**Data**: December 8, 2025  
**Status**: Ready for Deployment  
**Tempo Estimado**: 20-30 minutos

---

## 📋 PRÉ-REQUISITOS

- ✅ Conta GitHub (você já tem)
- ✅ Repositório CalibraWeb pusheado
- ✅ Conta Railway (grátis em railway.app)
- ✅ Cartão de crédito (railway cobra ~$5/mês, mas 1º mês é grátis)

---

## 🚀 PASSO 1: Criar Conta e Projeto no Railway

### 1.1 Criar Conta Railway
1. Acesse https://railway.app
2. Clique em "Start Project"
3. Selecione "Deploy from GitHub"
4. Autorize Railway a acessar seu GitHub
5. Selecione o repositório **vmotasilva/CalibraWeb**
6. Clique em "Deploy Now"

**⏳ Railway vai criar automaticamente:**
- Web service
- PostgreSQL database
- Redis (opcional)

---

## 🎯 PASSO 2: Configurar Variáveis de Ambiente

### 2.1 Acessar Variables no Railway

1. Vá em https://dashboard.railway.app
2. Clique no seu projeto **CalibraWeb**
3. Clique na aba **"Variables"**

### 2.2 Adicionar Variáveis Essenciais

Clique em "+ New Variable" e adicione cada uma (ou cole tudo de uma vez):

```env
# DJANGO CONFIGURATION
SECRET_KEY=<sua-chave-de-50-caracteres>
DEBUG=False
ALLOWED_HOSTS=*.railway.app

# DATABASE (Railway configura automaticamente)
# DATABASE_URL será preenchida automaticamente pelo PostgreSQL service

# SEGURANÇA & HTTPS
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# EMAIL (Gmail com App Password)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=seu-email@gmail.com

# LOGGING
LOG_LEVEL=INFO

# TIMEZONE
TIME_ZONE=America/Sao_Paulo

# REDIS (se Railroad criou automaticamente)
# REDIS_URL será preenchida automaticamente
```

### 2.3 Adicionar Variáveis no Railway UI

**Método 1: Uma por uma** (mais seguro):
```
1. Clique "+ New Variable"
2. Name: SECRET_KEY
3. Value: <cole sua chave de 50 caracteres>
4. Clique "+" para adicionar
5. Repita para cada variável
```

**Método 2: Colar tudo de uma vez** (mais rápido):
```
1. Clique no ícone "..." (Raw Editor)
2. Cole todas as variáveis em formato ENV
3. Salve
```

### 2.4 Verificar DATABASE_URL Automática

Railway cria PostgreSQL e injeta `DATABASE_URL` automaticamente:

1. Vá em "Variables"
2. Procure por `DATABASE_URL`
3. Se não aparecer, clique no banco PostgreSQL criado
4. A URL será mostrada lá

---

## 📊 PASSO 3: Configurar PostgreSQL

### 3.1 Railway Cria Automaticamente

Quando você clica "Deploy from GitHub", Railway cria:
- ✅ PostgreSQL database automaticamente
- ✅ Injeta DATABASE_URL nas variáveis
- ✅ Backup automático diário

### 3.2 Verificar Conexão

1. No dashboard Railway, clique na aba "PostgreSQL"
2. Veja as credenciais (User, Password, Host, Port)
3. Database name: `railway` (padrão)

---

## 💾 PASSO 4: Fazer Backup Pré-Deploy

Antes de fazer deploy, fazer backup local do banco atual:

```bash
cd c:\CalibraWeb

# Fazer backup
python backup_manager.py backup

# Listar backups
python backup_manager.py list

# Verificar arquivo foi criado
ls -la backups/
```

---

## 🔧 PASSO 5: Configurar Procfile (Se Necessário)

Railway detecta **Procfile** automaticamente. Já existe em seu projeto:

```procfile
web: gunicorn config.wsgi
```

✅ Já está correto! Railway vai rodar isso automaticamente.

---

## 📤 PASSO 6: Push para GitHub e Deploy Automático

### 6.1 Commit das Mudanças Finais

```bash
cd c:\CalibraWeb

# Verificar status
git status

# Adicionar qualquer arquivo não commitado
git add .

# Commit final
git commit -m "Deploy to Railway - Phase 12 Complete"

# Push para main (Railway monitora main branch)
git push origin phase-9-full-modularization:main
```

### 6.2 Acompanhar Deploy no Railway

1. Acesse https://dashboard.railway.app
2. Clique no seu projeto
3. Vá em "Deployments"
4. Veja o status do build

**Fases do Deploy:**
- 🔵 Building... (5-10 minutos)
- 🟢 Running (pronto!)
- 🔴 Failed (veja logs para erro)

### 6.3 Se Build Falhar

Clique em "Deployment" que falhou e veja os logs:

```
1. No dashboard, clique "Deployments"
2. Clique na falha
3. Veja a aba "Logs"
4. Procure por ERROR
5. Corrija localmente, fça push novamente
```

---

## 🗄️ PASSO 7: Executar Migrations em Produção

Quando o deploy ficar **🟢 Running**, executar migrations:

### 7.1 Acessar Console Railway

**Opção 1: Via CLI Railway** (recomendado)

```bash
# 1. Instalar Railway CLI
npm install -g @railway/cli
# Ou
scoop install railway

# 2. Login no Railway
railway login

# 3. Link ao seu projeto
railway link <project-id>

# 4. Rodar migrations
railway run python manage.py migrate

# 5. Criar superuser
railway run python manage.py createsuperuser
```

**Opção 2: Via Web Dashboard**

1. Vá em https://dashboard.railway.app
2. Clique seu projeto
3. Clique na aba "Terminal" (se disponível)
4. Digite:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

**Opção 3: SSH no Container**

1. Vá em "Deployments"
2. Clique em "Running"
3. Clique em "Connect"
4. Copie e execute o comando SSH

---

## ✅ PASSO 8: Verificar Deploy e Testes

### 8.1 Encontrar URL da Sua Aplicação

1. No dashboard Railway, clique seu projeto
2. Vá em "Settings" → "Domains"
3. Copie a URL gerada (ex: `calibraweb-production.up.railway.app`)

### 8.2 Testar Acesso

```bash
# 1. Testar admin
curl https://calibraweb-production.up.railway.app/admin/

# 2. Testar static files
curl https://calibraweb-production.up.railway.app/static/admin/css/base.css

# 3. Ou abrir no navegador
# https://calibraweb-production.up.railway.app/admin/
# Login com credentials do superuser criado
```

### 8.3 Verificar Logs em Produção

No dashboard Railway:
1. Clique seu projeto
2. Vá em "Logs"
3. Veja stderr/stdout em tempo real

---

## 🔐 PASSO 9: Configurações Pós-Deploy

### 9.1 Configurar Domínio Customizado (Opcional)

Se quiser URL customizada (ex: calibraweb.com.br):

1. No Railway, vá em "Settings" → "Domains"
2. Clique "+ Add Custom Domain"
3. Insira seu domínio (ex: calibraweb.com.br)
4. Railway mostra DNS records
5. Configure DNS no seu registrar
6. Aguarde propagação (15 min - 24h)

### 9.2 Backups Automáticos

Railway faz backup automático do PostgreSQL a cada 24h:

1. No dashboard, clique na aba "PostgreSQL"
2. Vá em "Backups"
3. Veja o histórico de backups automáticos

### 9.3 Monitoramento

Railway oferece:
- 📊 Metrics (CPU, RAM, requests)
- 📋 Logs em tempo real
- 🚨 Alertas (configurável)

---

## 🐛 TROUBLESHOOTING

### Erro 1: Build Falha por Dependência

```
Error: No module named 'xyz'
```

**Solução**:
1. Adicionar à requirements.txt:
   ```bash
   pip install xyz
   pip freeze > requirements.txt
   ```
2. Push e Railway rebuild

### Erro 2: Database Connection Refused

```
Error: could not connect to server
```

**Solução**:
1. Verificar DATABASE_URL foi setada em Variables
2. Verificar PostgreSQL service está running
3. No dashboard Railway, clique PostgreSQL → "Connect"
4. Teste a conexão

### Erro 3: Static Files 404

```
Admin CSS não carrega, 404 error
```

**Solução**:
```bash
# Rodar collectstatic em produção
railway run python manage.py collectstatic --noinput
```

### Erro 4: Secret Key Error

```
django.core.exceptions.ImproperlyConfigured: The SECRET_KEY setting must not be empty
```

**Solução**:
1. No Railway Variables, verificar SECRET_KEY está setada
2. Não pode estar vazia
3. Copie a chave gerada localmente e cole

---

## 📞 SUPORTE RAILWAY

- **Docs**: https://docs.railway.app
- **Status Page**: https://status.railway.app
- **Discord Community**: https://discord.gg/railway
- **Email**: support@railway.app

---

## 📊 CHECKLIST FINAL

- [ ] Conta Railway criada e logada
- [ ] Repositório GitHub conectado
- [ ] Variáveis de ambiente configuradas
- [ ] PostgreSQL service criado
- [ ] Build passou sem erros (🟢 Running)
- [ ] Migrations executadas
- [ ] Superuser criado
- [ ] Admin acessível em produção
- [ ] Static files carregando
- [ ] Email configurado e testado (opcional)
- [ ] Domínio customizado (opcional)
- [ ] Monitoramento ativado (opcional)

---

## 🎉 PRÓXIMOS PASSOS APÓS DEPLOY

### Dia 1:
- ✅ Verificar logs por erros
- ✅ Testar login admin
- ✅ Testar operações básicas
- ✅ Fazer backup manual

### Dia 2-3:
- ✅ Monitorar performance
- ✅ Testar com mais dados
- ✅ Validar email (se configurado)

### Semana 1:
- ✅ Implementar Redis caching (opcional)
- ✅ Configurar alertas
- ✅ Documentar procedimentos operacionais

---

## ⏱️ TIMELINE ESTIMADA

| Atividade | Tempo |
|-----------|-------|
| Criar conta Railway | 5 min |
| Conectar GitHub | 5 min |
| Configurar variáveis | 10 min |
| Build automático | 10 min |
| Migrations e setup | 5 min |
| Testes pós-deploy | 5 min |
| **TOTAL** | **40 min** |

---

## 💡 DICAS IMPORTANTES

1. **Primeira vez é grátis**: Railway dá $5/mês crédito grátis
2. **Auto-scaling**: Railway escala automaticamente
3. **Backups**: PostgreSQL faz backup automático
4. **Logs**: Veja em tempo real no dashboard
5. **Rollback**: Pode voltar para deployment anterior
6. **Preview**: Pode fazer preview antes de deploy em main

---

**Document**: RAILWAY_DEPLOYMENT_GUIDE.md  
**Status**: Ready to Deploy  
**Next**: Follow the steps above! 🚀
