# 🚀 RAILWAY DEPLOYMENT - INSTRUÇÕES VISUAIS

## RESUMO EXECUTIVO

✅ **Status**: Pronto para Deploy  
⏱️ **Tempo Total**: ~40 minutos  
📍 **Plataforma**: Railway.app (recomendado)  
💰 **Custo**: Primeiro mês grátis ($5/mês depois)

---

## 📋 CHECKLIST - SIGA NA ORDEM

### ✅ ETAPA 1: PREPARAÇÃO LOCAL (5 minutos)

```
[ ] 1. Abrir terminal em c:\CalibraWeb
[ ] 2. Fazer backup: python backup_manager.py backup
[ ] 3. Validar: python manage.py check
[ ] 4. Gerar SECRET_KEY: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
[ ] 5. Salvar SECRET_KEY em local seguro (arquivo de texto, gestor de senhas, etc)
```

**⏸️ PAUSA**: Guarde a SECRET_KEY gerada!

---

### ✅ ETAPA 2: CRIAR CONTA RAILWAY (5 minutos)

```
[ ] 1. Abrir navegador
[ ] 2. Ir em https://railway.app
[ ] 3. Clicar "Start a New Project"
[ ] 4. Clicar "Deploy from GitHub"
[ ] 5. Autorizar Railway a acessar seu GitHub
[ ] 6. Selecionar repositório "vmotasilva/CalibraWeb"
[ ] 7. Clicar "Deploy"
```

**⏸️ PAUSA**: Railway está criando infraestrutura...

---

### ✅ ETAPA 3: CONFIGURAR VARIÁVEIS (10 minutos)

```
[ ] 1. No dashboard Railway, clique projeto CalibraWeb
[ ] 2. Clique aba "Variables"
[ ] 3. Para cada linha abaixo, clique "+ New Variable" e adicione:

    SECRET_KEY = <cole sua chave de 50 caracteres>
    DEBUG = False
    ALLOWED_HOSTS = *.railway.app
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    EMAIL_HOST = smtp.gmail.com
    EMAIL_PORT = 587
    EMAIL_HOST_USER = seu-email@gmail.com
    EMAIL_HOST_PASSWORD = sua-app-password
    EMAIL_USE_TLS = True
    TIME_ZONE = America/Sao_Paulo

[ ] 4. Verifique que DATABASE_URL foi preenchida automaticamente
[ ] 5. Salve
```

**⏸️ PAUSA**: Railway está compilando a aplicação...

---

### ✅ ETAPA 4: AGUARDAR BUILD (10 minutos)

```
[ ] 1. No dashboard, vá em "Deployments"
[ ] 2. Veja o status:
    🔵 Building... (aguarde até virar verde)
    🟢 Running (sucesso!)
[ ] 3. Se der erro 🔴, clique para ver logs
```

**TEMPO DE ESPERA**: 5-10 minutos normalmente

---

### ✅ ETAPA 5: CONFIGURAR BANCO DE DADOS (5 minutos)

```
[ ] 1. No dashboard, clique na aba "PostgreSQL"
[ ] 2. Clique em "Connect" para ver credenciais
[ ] 3. Copie DATABASE_URL (deve estar em Variables já)
[ ] 4. Seu banco está criado e pronto!
```

---

### ✅ ETAPA 6: RODAR MIGRATIONS EM PRODUÇÃO (10 minutos)

**Opção A: Recomendada - CLI Railway**

```bash
# Passo 1: Instalar Railway CLI (uma vez)
npm install -g @railway/cli

# Passo 2: Login
railway login
# Siga as instruções (click no navegador para autorizar)

# Passo 3: Ir para pasta do projeto
cd c:\CalibraWeb

# Passo 4: Link ao projeto Railway
railway link
# Selecione: CalibraWeb

# Passo 5: Rodar migrations
railway run python manage.py migrate
# Aguarde completar

# Passo 6: Criar superuser
railway run python manage.py createsuperuser
# Digite:
#   Username: admin
#   Email: seu-email@email.com
#   Password: <senha forte>
#   Password again: <mesma senha>
```

**Opção B: Via Web Dashboard**

1. No Railway, clique projeto
2. Procure aba "Terminal"
3. Copie e execute cada comando acima

---

### ✅ ETAPA 7: ENCONTRAR URL DA APLICAÇÃO (1 minuto)

```
[ ] 1. No dashboard Railway, clique CalibraWeb
[ ] 2. Procure link parecido com:
    https://calibraweb-xxx.up.railway.app
[ ] 3. Salve este link (é seu site em produção!)
```

---

## ✅ TESTES PÓS-DEPLOYMENT (5 minutos)

### Teste 1: Acessar Admin

```
1. Abra navegador
2. Vá em: https://calibraweb-xxx.up.railway.app/admin/
3. Faça login com suas credenciais
4. Se entrar com sucesso ✅
```

### Teste 2: Static Files

```
1. Abra navegador
2. Vá em: https://calibraweb-xxx.up.railway.app/static/admin/css/base.css
3. Se aparecer conteúdo CSS ✅
```

### Teste 3: Operação Básica

```
1. No admin, vá em Organização > Setores
2. Tente adicionar um novo setor
3. Se conseguir criar ✅
```

### Teste 4: Logs

```
1. No dashboard Railway, vá em "Logs"
2. Procure por erros (ERROR, Exception)
3. Se limpo ✅
```

---

## 🎉 SUCESSO!

Se passou em todos os testes, parabéns! 🚀

**Seu CalibraWeb está RODANDO EM PRODUÇÃO!**

---

## 📊 O QUE VOCÊ TEM AGORA

| Item | Incluído | Benefício |
|------|----------|-----------|
| Aplicação Django | ✅ | Rodando online 24/7 |
| PostgreSQL | ✅ | Banco em nuvem seguro |
| HTTPS/SSL | ✅ | Automático, sempre atualizado |
| Backups automáticos | ✅ | Diário, restaurável |
| Logs em tempo real | ✅ | Monitore problemas |
| Auto-scaling | ✅ | Cresce com demanda |
| Domínio customizado | 🔄 | Opcional, configure depois |
| Email | 📝 | Pronto, só testar |
| Redis caching | 🔄 | Opcional, para 60% mais rápido |

---

## 🔧 PRÓXIMOS PASSOS (Opcional)

### Dia 1:
- Monitorar logs por 1-2 horas
- Testar operações críticas
- Fazer backup manual adicional

### Semana 1:
- Configurar domínio customizado (se tiver)
- Implementar Redis caching (se quiser ~60% mais rápido)
- Configurar alertas
- Testar email end-to-end

### Mês 1:
- Coletar feedback de usuários
- Otimizar com base em uso real
- Documentar procedimentos operacionais

---

## 🆘 TROUBLESHOOTING RÁPIDO

### ❌ "Build falhou"
→ Clique no Deployment falho e veja os logs  
→ Procure por "ERROR"  
→ Corrija localmente e faça `git push` novamente

### ❌ "Admin não abre"
→ Verificar DATABASE_URL em Variables  
→ Rodar migrations novamente  
→ Verificar logs

### ❌ "Static files não carregam"
```bash
railway run python manage.py collectstatic --noinput
```

### ❌ "Erro de EMAIL"
→ Verificar EMAIL_HOST_PASSWORD está correto  
→ Se usar Gmail, gerar "App Password" (não senha normal)

---

## 📞 OBTER AJUDA

**Railway Documentation**: https://docs.railway.app  
**Railway Discord**: https://discord.gg/railway  
**CalibraWeb Docs**: Ver RAILWAY_DEPLOYMENT_GUIDE.md (mais detalhado)

---

## ⏰ TIMELINE

```
Agora                          T+40min
|                              |
0-5min    Preparação Local     ✅
5-10min   Criar Railway        ✅
10-20min  Configurar Vars      ✅
20-30min  Build automático     ✅
30-35min  Migrations           ✅
35-40min  Testes               ✅
|                              |
                    🎉 LIVE! 🚀
```

---

## 💡 DICAS IMPORTANTES

1. **Cartão de crédito**: Railway precisa, mas 1º mês é grátis
2. **DATABASE_URL**: Railway preenche automaticamente, não edite
3. **Backups**: PostgreSQL faz backup automático diário
4. **Rollback**: Pode voltar para deploy anterior em 1 clique
5. **Logs**: Veja em tempo real, super útil para debug
6. **Escala**: Railway escala automaticamente se tiver muitos acessos

---

## ✨ VOCÊ CONSEGUE!

Pronto? Vamos começar! 👉 Abra https://railway.app

🚀 **Happy Deploying!**

---

**Documento**: RAILWAY_DEPLOYMENT_VISUAL.md  
**Status**: Ready to Deploy  
**Tempo**: ~40 minutos total  
**Dificuldade**: ⭐ Fácil (Railway faz quase tudo automaticamente)
