# RAILWAY DEPLOYMENT - QUICK CHECKLIST
## Guia Rápido Passo-a-Passo

---

## ✅ PRÉ-DEPLOYMENT (Local)

### Passo 1️⃣: Fazer Backup de Segurança

```bash
cd c:\CalibraWeb
python backup_manager.py backup
python backup_manager.py list
```

✅ **Resultado Esperado**: Arquivo em `backups/sqlite_db_YYYYMMDD_HHMMSS.sqlite3.gz`

---

### Passo 2️⃣: Validação Final

```bash
cd c:\CalibraWeb

# 1. Check Django
python manage.py check
# Esperado: System check identified no issues

# 2. Check Deploy
python manage.py check --deploy
# Esperado: 2 warnings (acceptable)

# 3. Testes
python test_production_env.py
# Esperado: All 10 tests PASSED

# 4. Commit final
git status
# Esperado: working tree clean
```

✅ **Resultado Esperado**: Todos os checks passam

---

### Passo 3️⃣: Gerar SECRET_KEY

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

📝 **GUARDE ESTA CHAVE! Você vai usar em 5 minutos!**

---

## 🚀 RAILWAY DEPLOYMENT (Na nuvem)

### Passo 4️⃣: Criar Conta Railway

1. Abra https://railway.app
2. Clique em **"Start a New Project"**
3. Clique em **"Deploy from GitHub"**
4. Authorize Railway para acessar seu GitHub

✅ **Pronto**: Você está logado no Railway

---

### Passo 5️⃣: Conectar CalibraWeb

1. No Railway, após autorizar GitHub:
2. Procure por **"vmotasilva/CalibraWeb"**
3. Clique para selecionar
4. Clique em **"Deploy"**

⏳ **Aguarde**: Railway vai criar PostgreSQL, Redis, etc (1-2 min)

✅ **Pronto**: Projeto criado no Railway

---

### Passo 6️⃣: Configurar Variáveis de Ambiente

1. No dashboard Railway, clique seu projeto **CalibraWeb**
2. Clique na aba **"Variables"**
3. Clique em **"+ New Variable"** para cada uma:

```
SECRET_KEY = <sua-chave-de-50-caracteres>
DEBUG = False
ALLOWED_HOSTS = *.railway.app
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
EMAIL_HOST = smtp.gmail.com
EMAIL_PORT = 587
EMAIL_HOST_USER = seu-email@gmail.com
EMAIL_HOST_PASSWORD = sua-app-password
EMAIL_USE_TLS = True
TIME_ZONE = America/Sao_Paulo
```

✅ **Pronto**: Todas as variáveis configuradas

---

### Passo 7️⃣: Verificar PostgreSQL

1. No dashboard Railway, procure por serviço **"PostgreSQL"**
2. Clique nele
3. Vá em aba **"Variables"**
4. Você verá **DATABASE_URL** automaticamente preenchida

✅ **Pronto**: Banco de dados pronto!

---

### Passo 8️⃣: Aguardar Build Completar

1. No dashboard, vá em **"Deployments"**
2. Veja o status:
   - 🔵 Building... (aguarde 5-10 min)
   - 🟢 Running (sucesso!)
   - 🔴 Failed (veja logs)

✅ **Pronto**: Aplicação rodando em produção!

---

### Passo 9️⃣: Executar Migrations

**Opção A: Via CLI Railway** (mais fácil)

```bash
# 1. Instalar CLI (uma vez)
npm install -g @railway/cli

# 2. Login
railway login

# 3. Rodar migrations
railway run python manage.py migrate

# 4. Criar superuser
railway run python manage.py createsuperuser
# Digite username, email, password
```

**Opção B: Via Web Dashboard**

1. No Railway, clique seu projeto
2. Procure aba **"Terminal"** ou **"Connect"**
3. Execute:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

✅ **Pronto**: Banco de dados preparado!

---

### Passo 🔟: Encontrar URL da Aplicação

1. No dashboard Railway, clique seu projeto **CalibraWeb**
2. Procure pela aba **"Deployments"** → **"Running"**
3. Procure um link tipo: `https://calibraweb-xxx.up.railway.app`

📝 **GUARDE ESTA URL! É seu site em produção!**

---

## ✅ PÓS-DEPLOYMENT (Validação)

### Passo 1️⃣1️⃣: Testar Admin

1. Abra seu navegador
2. Vá em: `https://<sua-url-railway>/admin/`
3. Faça login com as credenciais do superuser criado
4. Se entrar, tudo está funcionando! ✅

---

### Passo 1️⃣2️⃣: Testar Static Files

1. Abra seu navegador
2. Vá em: `https://<sua-url-railway>/static/admin/css/base.css`
3. Se aparecer CSS (texto), está OK! ✅

---

### Passo 1️⃣3️⃣: Verificar Logs

1. No dashboard Railway, clique seu projeto
2. Vá em **"Logs"**
3. Procure por erros (ERROR, Exception)
4. Se tudo limpo, tudo OK! ✅

---

## 🎉 SUCESSO!

Parabéns! Seu CalibraWeb está **RODANDO EM PRODUÇÃO** no Railway! 🚀

### O que você tem agora:

- ✅ Aplicação rodando online
- ✅ Banco de dados PostgreSQL em nuvem
- ✅ Backups automáticos diários
- ✅ HTTPS/SSL automático
- ✅ Auto-scaling (cresce se tiver muitos acessos)
- ✅ Logs em tempo real

### Próximos passos (opcional):

1. Configurar domínio customizado (Railway → Domains → Add Custom Domain)
2. Implementar Redis caching (para 60% mais rápido)
3. Configurar email (testar sending)
4. Monitorar performance

---

## 🆘 SE ALGO DER ERRADO

### Build falhou?

1. No Railway, clique "Deployments"
2. Clique na falha
3. Procure por "ERROR" nos logs
4. Corrija localmente em `config/settings.py` ou `requirements.txt`
5. Faça `git push` novamente
6. Railway vai recompilar automaticamente

### Admin não abre?

1. Verificar DATABASE_URL está em Variables
2. Verificar migrations foram executadas
3. Verificar superuser foi criado
4. Verificar logs em Railway → Logs

### Static files não carregam?

```bash
# Rodar collectstatic novamente
railway run python manage.py collectstatic --noinput
```

### Conectar ao banco de dados remotamente (se precisar):

```bash
# Connection string (do Railway → PostgreSQL → Connect)
psql postgresql://user:password@host:port/railway
```

---

## ⏱️ TEMPO TOTAL

| Tarefa | Tempo |
|--------|-------|
| Backup local | 2 min |
| Criar conta Railway | 5 min |
| Conectar GitHub | 5 min |
| Configurar variáveis | 10 min |
| Build automático | 10 min |
| Migrations | 5 min |
| Testes | 5 min |
| **TOTAL** | **42 min** |

---

## 📞 SUPORTE

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **CalibraWeb Docs**: Veja RAILWAY_DEPLOYMENT_GUIDE.md (mais detalhado)

---

**Status**: Ready to Deploy! 🚀  
**Última atualização**: December 8, 2025
