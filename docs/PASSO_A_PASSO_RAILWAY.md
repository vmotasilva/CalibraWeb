# 🚀 Passo a Passo - Corrigir Erro de Banco de Dados no Railway

## ❌ Problema Atual

Os logs mostram este erro repetidamente:
```
Detected malformed DATABASE_URL with placeholder 'host', attempting to build from PG* vars
Insufficient PG* environment variables to build database URL
could not translate host name "host" to address: No address associated with hostname
```

**CAUSA RAIZ:** Você não tem um banco de dados PostgreSQL criado no Railway!

---

## ✅ Solução - Criar PostgreSQL no Railway

### **PASSO 1: Adicionar PostgreSQL ao Projeto**

1. Acesse o dashboard do seu projeto no Railway: https://railway.app/
2. Abra o projeto **CalibraWeb**
3. Clique no botão **"+ New"** (canto superior direito)
4. Selecione **"Database"**
5. Escolha **"Add PostgreSQL"**
6. ⏳ Aguarde 30-60 segundos enquanto o Railway provisiona o banco de dados
7. ✅ Você verá um novo card "PostgreSQL" aparecer no dashboard

---

### **PASSO 2: Conectar PostgreSQL ao Serviço Web (Django)**

**CRÍTICO:** Você precisa criar uma "referência" entre o PostgreSQL e seu serviço web Django.

1. No dashboard do Railway, clique no seu **serviço web** (Django/CalibraWeb)
2. Clique na aba **"Variables"** (Variáveis)
3. Clique em **"+ New Variable"** → **"Add Reference"**
4. Na janela que abrir:
   - **Service:** Selecione **"PostgreSQL"** (o banco que você acabou de criar)
   - **Marque TODAS estas variáveis:**
     - ☑️ `DATABASE_URL`
     - ☑️ `PGHOST`
     - ☑️ `PGPORT`
     - ☑️ `PGUSER`
     - ☑️ `PGPASSWORD`
     - ☑️ `PGDATABASE`
5. Clique em **"Add"**

---

### **PASSO 3: Aguardar Redesploy Automático**

- ✅ O Railway vai **automaticamente** fazer um novo deploy
- ⏳ Aguarde ~2-3 minutos
- 📊 Acompanhe os logs em tempo real

---

### **PASSO 4: Verificar os Novos Logs**

Após o redesploy, você deve ver logs assim:

```
DB ENV CHECK: PGHOST=postgres.railway.internal, PGPORT=5432, PGUSER=postgres, PGPASSWORD=***, PGDATABASE=railway
Using PostgreSQL database from PG* environment variables
Database configuration successful
==> Running database migrations...
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, qms, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  ...
==> Collecting static files...
==> Starting Gunicorn server...
```

✅ **O erro "could not translate host name 'host'" deve desaparecer!**

---

## 📋 Checklist de Verificação

Depois que o deploy funcionar:

- [ ] PostgreSQL criado no Railway
- [ ] Variáveis referenciadas no serviço web
- [ ] Logs mostram conexão bem-sucedida com o banco
- [ ] Migrações executadas com sucesso
- [ ] Gunicorn iniciado sem erros
- [ ] Site acessível em: https://calibraweb.up.railway.app/

---

## 🔧 Comandos Adicionais (Após Deploy Bem-Sucedido)

Se precisar executar comandos manualmente no Railway:

1. No dashboard, clique no serviço web
2. Vá em **"Settings"** → **"Deploy"** → Abra o terminal

```bash
# Verificar conexão com banco de dados
python manage.py check --database default

# Aplicar migrações (se necessário)
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser
# Username: admin
# Email: admin@calibraweb.com
# Password: [escolha uma senha forte]
```

---

## ❓ Por Que Isso Aconteceu?

O Railway **não cria automaticamente** um banco de dados PostgreSQL quando você faz deploy de um app Django. Você precisa:

1. Adicionar o plugin PostgreSQL manualmente
2. Conectar o plugin ao serviço web via "Variable References"

Seu código Django estava perfeito desde o início - só faltava a infraestrutura do banco de dados!

---

## 📞 Próximos Passos

Após o PostgreSQL estar funcionando:

1. ✅ Acesse: https://calibraweb.up.railway.app/admin/
2. ✅ Faça login com o superusuário criado
3. ✅ Configure domínio customizado (se desejar)
4. ✅ Comece a usar o CalibraWeb em produção!

---

## 🆘 Se Ainda Tiver Problemas

Se após criar o PostgreSQL você ainda ver erros, verifique:

1. **Variáveis estão corretas?**
   - Vá em Variables do serviço web
   - Confirme que todas as 6 variáveis PG* estão listadas
   - Devem ter o ícone 🔗 (link) indicando que são referências

2. **Deploy foi concluído?**
   - Aguarde o deploy terminar completamente
   - Status deve estar "Active" (verde)

3. **Logs mostram as variáveis?**
   - Procure por "DB ENV CHECK" nos logs
   - Deve mostrar valores reais, não "None"

---

**🎯 A solução é simples: criar o PostgreSQL e conectá-lo ao serviço web no Railway!**
