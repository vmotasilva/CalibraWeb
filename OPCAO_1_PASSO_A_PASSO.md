# ✅ OPÇÃO 1: GUIA VISUAL PASSO-A-PASSO

## 🎯 OBJETIVO
Iniciar os 5 serviços necessários do CalibraWeb local (Redis, Celery, Django, Dashboard)

**Tempo total:** 30 minutos  
**Dificuldade:** Fácil  
**Status:** Redis já rodando ✅

---

## 📋 CREDENCIAIS DE TESTE

### Superuser (Admin)
```
Username: admin
Password: TestPass123456!@#
Email: admin@calibraweb.local
```

**Acessar:**
- Django Admin: http://127.0.0.1:8000/admin/
- Cache Dashboard: http://127.0.0.1:8000/dashboard/

---

## 🚀 PASSO 1: Abrir Terminal 2 (Celery Worker)

### 1.1 Abrir nova janela PowerShell
- Windows: Win + R → escreva `powershell` → Enter
- Ou abra Windows Terminal e clique "+" para nova aba

### 1.2 Navegar para projeto
```powershell
cd c:\CalibraWeb
```

### 1.3 Ativar ambiente virtual
```powershell
.venv\Scripts\Activate.ps1
```

**Esperado:** Você deve ver `(.venv)` no início do prompt

### 1.4 Iniciar Celery Worker
```powershell
celery -A config worker -l info
```

### 1.5 Aguardar mensagem
```
celery@NOME-DO-COMPUTADOR ready to accept tasks
```

✅ **Terminal 2 pronto!** Deixe rodando e vá para o próximo terminal.

---

## 🚀 PASSO 2: Abrir Terminal 3 (Celery Beat)

### 2.1 Abrir OUTRA nova janela PowerShell

### 2.2 Navegar e ativar (mesmos comandos do Passo 1)
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
```

### 2.3 Iniciar Celery Beat
```powershell
celery -A config beat -l info
```

### 2.4 Aguardar saída
```
scheduler/syncer: Synced 5 tasks from database
Scheduler: Launching 5 scheduled tasks
```

✅ **Terminal 3 pronto!** Deixe rodando e vá para o próximo terminal.

---

## 🚀 PASSO 3: Abrir Terminal 4 (Django Server)

### 3.1 Abrir OUTRA nova janela PowerShell

### 3.2 Navegar e ativar (mesmos comandos)
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
```

### 3.3 Iniciar servidor Django
```powershell
python manage.py runserver
```

### 3.4 Aguardar mensagem
```
Starting development server at http://127.0.0.1:8000/
```

✅ **Terminal 4 pronto!** Deixe rodando e vá para o próximo terminal.

---

## 🚀 PASSO 4: Abrir Terminal 5 (Cache Dashboard)

### 4.1 Abrir OUTRA nova janela PowerShell

### 4.2 Navegar e ativar (mesmos comandos)
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
```

### 4.3 Iniciar Cache Dashboard
```powershell
python manage.py cache_dashboard --live --interval 2
```

### 4.4 Aguardar saída
```
Dashboard server running on http://127.0.0.1:8000/dashboard/
Listening for cache updates...
```

✅ **Terminal 5 pronto!** Agora você tem 5 serviços rodando!

---

## 📊 VERIFICAÇÃO: TODOS OS SERVIÇOS PRONTOS

Você deve ter 5 terminais abertos:

| Terminal | Serviço | Status | Mensagem |
|----------|---------|--------|----------|
| 1 | Redis Mock | ✅ Rodando | localhost:6379 |
| 2 | Celery Worker | ✅ Rodando | ready to accept tasks |
| 3 | Celery Beat | ✅ Rodando | Launching scheduled tasks |
| 4 | Django Server | ✅ Rodando | Starting development server |
| 5 | Cache Dashboard | ✅ Rodando | Listening for updates |

**Se tudo está aqui, você tem 100% de sucesso!**

---

## 🌐 ACESSAR APLICAÇÃO

### Django Admin
- **URL:** http://127.0.0.1:8000/admin/
- **Username:** admin
- **Password:** TestPass123456!@#

### Cache Dashboard (Monitoramento)
- **URL:** http://127.0.0.1:8000/dashboard/
- **Mostrador:** Métricas de cache em tempo real
- **Atualização:** A cada 2 segundos

### API Base
- **URL:** http://127.0.0.1:8000/api/
- **Autenticação:** Use as mesmas credenciais de admin

---

## 🧪 TESTAR FUNCIONALIDADE

### 1. Verificar Dashboard
- Abra: http://127.0.0.1:8000/dashboard/
- Observe: Gráficos de cache hits/misses atualizando em tempo real
- Espere: Alguns segundos para dados iniciais aparecerem

### 2. Acessar Admin
- Abra: http://127.0.0.1:8000/admin/
- Login com credenciais acima
- Explore: Usuários, grupos, permissões

### 3. Rodar Testes (em novo terminal)
```powershell
cd c:\CalibraWeb
.venv\Scripts\Activate.ps1
python manage.py test qms --verbosity=2
```

**Esperado:** 94 testes passando

### 4. Verificar Celery Tasks
- Veja no Terminal 2 (Worker) mensagens de tasks sendo executadas
- Veja no Terminal 3 (Beat) agendamentos sendo disparados
- Dados aparecem no Dashboard em tempo real

---

## 🔍 TROUBLESHOOTING

### Se algum terminal exibir erro:

#### **Erro: "Command not found: celery"**
```powershell
.venv\Scripts\Activate.ps1
pip install celery -U
```

#### **Erro: "Port 8000 already in use"**
```powershell
# Use porta diferente
python manage.py runserver 8001
```

#### **Erro: "Redis connection refused"**
```powershell
# Redis mock server pode estar parado
# Verifique Terminal 1
# Se parou, reinicie em novo terminal:
python mock_redis_server.py
```

#### **Django admin não carrega**
```powershell
# Faça as migrações
python manage.py migrate
# Crie novo admin
python create_test_admin.py
```

#### **Dashboard vazio/sem dados**
- Aguarde 30 segundos para primeiro acesso
- Faça algumas requisições HTTP para gerar dados
- Verifique se Django/Celery estão rodando

---

## 📝 CHECKLIST: CONFIRME SE TUDO ESTÁ OK

Antes de considerar completo, verifique:

- [ ] Terminal 1: Redis rodando (stdout com logs)
- [ ] Terminal 2: Celery Worker pronto (mensagem "ready to accept tasks")
- [ ] Terminal 3: Celery Beat agendando (mensagem "Launching tasks")
- [ ] Terminal 4: Django Server rodando (http://127.0.0.1:8000/)
- [ ] Terminal 5: Dashboard disponível (http://127.0.0.1:8000/dashboard/)
- [ ] Admin login funciona (http://127.0.0.1:8000/admin/)
- [ ] Dashboard mostra dados (gráficos carregando)
- [ ] Testes passam (python manage.py test qms)
- [ ] Sem erros em nenhum terminal
- [ ] Git status limpo (git status)

✅ **Se todos os items estão marcados, Opção 1 está COMPLETA!**

---

## 📊 DEPOIS: PRÓXIMA ETAPA (Opção 2)

Quando estiver satisfeito com testes locais:

1. **Parar todos os serviços**
   - Pressione Ctrl+C em cada terminal

2. **Preparar para staging**
   - Seguir STAGING_ACTION_PLAN.md
   - Escolher plataforma (Railway, Heroku, Docker, etc)

3. **Deploy para staging**
   - 2-3 horas de setup
   - 24 horas de validação
   - Depois: Production Week 2

---

## 🎉 VOCÊ COMPLETOU OPÇÃO 1!

Parabéns! Sua ambiente local está:

✅ Rodando todos 5 serviços  
✅ Testando cache funcionando  
✅ Dashboard monitorando em tempo real  
✅ Admin acessível e responsivo  
✅ Testes passando  
✅ Celery agendando tarefas  
✅ Redis cache operacional  

**Você está pronto para staging deployment!**

---

**Próximo documento:** `STAGING_ACTION_PLAN.md`  
**Tempo total para Opção 1:** 30 minutos ✅  
**Status:** COMPLETO
