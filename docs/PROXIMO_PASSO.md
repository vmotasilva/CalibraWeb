# 📋 PRÓXIMOS PASSOS - CHECKLIST INTERATIVO

**Status**: 🔵 Railway compilando ou 🟢 Pronto  
**Data**: December 8, 2025  
**Tempo Estimado**: 5-10 minutos

---

## ✅ PASSO 1: AGUARDAR BUILD NO RAILWAY (Automático)

### Monitorar em Tempo Real

**URL do Dashboard**: https://dashboard.railway.app

**Ações**:
1. Abra https://dashboard.railway.app em seu navegador
2. Faça login com suas credenciais
3. Clique no projeto **CalibraWeb**
4. Vá em **Deployments**
5. Procure pelo deployment mais recente

**Status esperados**:
- 🔵 **Building** → Aplicação compilando (2-8 minutos)
- 🟢 **Running** → Pronto! (prossiga para o Passo 2)
- 🔴 **Failed** → Veja os logs (clique no deployment e procure por ERROR)

**Tempo estimado**: 5-10 minutos

---

## ✅ PASSO 2: INSTALAR RAILWAY CLI (uma vez apenas)

### Opção A: npm (Recomendado)

```bash
npm install -g @railway/cli
```

**Verificar instalação**:
```bash
railway --version
```

### Opção B: Scoop (Windows)

```bash
scoop install railway
```

**Resultado esperado**: Mostra versão (ex: `railway 3.1.0`)

---

## ✅ PASSO 3: FAZER LOGIN NO RAILWAY

```bash
railway login
```

**O que vai acontecer**:
1. Terminal abre um navegador automaticamente
2. Você verá página de login do Railway
3. Autorize a aplicação (clique em "Authorize")
4. Retorne ao terminal
5. Confirme sucesso: "✓ Logged in"

**Se não abrir navegador**:
- Copie o link do terminal
- Abra manualmente no navegador
- Retorne ao terminal após autorizar

---

## ✅ PASSO 4: EXECUTAR MIGRATIONS

**Espere**: Aplicação estar 🟢 **Running** no Dashboard antes!

```bash
cd c:\CalibraWeb
railway run python manage.py migrate
```

**Saída esperada**:
```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying sessions.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying organization.0001_initial... OK
  Applying rh.0001_initial... OK
  Applying metrologia.0001_initial... OK
  Applying procurements.0001_initial... OK
  Applying training.0001_initial... OK
  Applying qms.0001_initial... OK
  (11 migrations total)
```

**Status**: ✅ **Migrations completas**

---

## ✅ PASSO 5: CRIAR SUPERUSER

```bash
cd c:\CalibraWeb
railway run python manage.py createsuperuser
```

**O que você verá**:
```
Username: |
```

**Digite seus dados**:

```
Username: admin
Email: seu-email@email.com
Password: senha123456
Password (again): senha123456
Superuser created successfully.
```

**Importante**: Use senha forte! Sugestão:
```
SuaSenha@2025Railway!
```

**Status**: ✅ **Superuser criado**

---

## ✅ PASSO 6: ENCONTRAR URL DA APLICAÇÃO

### Opção A: Via Terminal

```bash
railway open
```

Isso abre a aplicação no navegador automaticamente.

### Opção B: Via Dashboard

1. No https://dashboard.railway.app
2. Clique em **CalibraWeb**
3. Clique no ambiente (ex: **production**)
4. No painel direito, procure por **Service Domain**
5. Copie o link: `https://calibraweb-xxx.up.railway.app`

**Formato esperado**:
```
https://calibraweb-XXXXXXXX.up.railway.app
```

---

## ✅ PASSO 7: ACESSAR ADMIN

```
URL: https://calibraweb-XXXXXXXX.up.railway.app/admin/

Username: admin
Password: (aquela que você criou no Passo 5)
```

**Se conseguir fazer login**: 🎉 **SUCESSO TOTAL!**

**Se não conseguir acessar**:
- Aguarde 1-2 minutos (pode estar inicializando)
- Procure erros em: `railway logs`
- Verifique migrations: `railway run python manage.py migrate --check`

---

## 🔍 TROUBLESHOOTING RÁPIDO

### Build falhou (🔴 Failed)

```bash
# Ver logs detalhados
railway logs -n 50

# Procure por "ERROR" ou "FAILED"
```

**Solução comum**:
```bash
# Recompilar
git push origin phase-9-full-modularization:main

# Railway detecta automaticamente e recompila
```

### Migrations falharam

```bash
# Ver status das migrations
railway run python manage.py migrate --check

# Reexecutar manualmente
railway run python manage.py migrate --verbosity 2
```

### Admin não carrega static files

```bash
# Coletar static files novamente
railway run python manage.py collectstatic --noinput
```

### Verificar variáveis de ambiente

```bash
railway variables
```

**Esperado**:
```
DATABASE_URL=postgresql://...
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=*.railway.app
```

---

## 📊 RESUMO DOS PASSOS

| Passo | Comando | Tempo | Status |
|-------|---------|-------|--------|
| 1 | Aguardar Build | 5-10 min | ⏳ Em andamento |
| 2 | Instalar Railway CLI | 2 min | ⏳ Quando pronto |
| 3 | Login Railway | 1 min | ⏳ Quando pronto |
| 4 | Migrations | 1 min | ⏳ Quando pronto |
| 5 | Criar Superuser | 1 min | ⏳ Quando pronto |
| 6 | Encontrar URL | <1 min | ⏳ Quando pronto |
| 7 | Acessar Admin | <1 min | ⏳ Quando pronto |

**Tempo total**: ~10-20 minutos

---

## 🎯 CHECKLIST FINAL

Conforme você avança, marque como completo:

- [ ] Aguardei build completar (🟢 Running)
- [ ] Instalei Railway CLI
- [ ] Fiz login no Railway (`railway login`)
- [ ] Executei migrations
- [ ] Criei superuser
- [ ] Encontrei URL da aplicação
- [ ] Consegui acessar `/admin/`
- [ ] Consegui fazer login
- [ ] Vejo o painel administrativo

---

## 🆘 PRECISA DE AJUDA?

**Se algo não funcionar**:
1. Procure a mensagem de erro em **Troubleshooting** acima
2. Execute `railway logs` para ver detalhes
3. Tente os comandos sugeridos

**Erros comuns esperados**:
- ⏳ "Deployments not found" → Ainda compilando
- ❌ "Not authenticated" → Execute `railway login` novamente
- 404 na URL → Aguarde 1-2 minutos

---

## ✅ PRÓXIMOS PASSOS APÓS ADMIN FUNCIONAR

1. **Testar funcionalidades básicas**:
   - Criar um usuário de teste
   - Adicionar um instrumento
   - Registrar calibração

2. **Verificar performance**:
   - Abrir admin/metrologia/instrumento/
   - Verificar se carrega rápido (< 2 segundos)
   - Confirmar que static files carregam

3. **Configurar domínio customizado** (opcional):
   - Em Railway → Projeto → Settings → Networking
   - Conectar domínio próprio

4. **Implementar caching Redis** (opcional, fase 13):
   - Pode melhorar performance em 60%
   - Arquivo pronto: `REDIS_CACHING_STRATEGY.md`

---

**Status do Projeto**: 🟢 **Em Produção!**

Próxima verificação: Acessar admin e confirmar funcionalidade.

