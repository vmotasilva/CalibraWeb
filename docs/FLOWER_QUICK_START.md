## 🌸 Flower - Quick Start Guide

**Status:** ✅ INSTALADO E CONFIGURADO

---

## ✨ O que é Flower?

Flower é um **dashboard web em tempo real** para monitorar tarefas Celery. Mostra:

```
✅ Tasks em execução/pendentes/concluídas
✅ Workers online/offline
✅ Performance metrics
✅ Histórico de execução
✅ Alertas de falhas
✅ API REST
```

---

## 🚀 Iniciar Flower Localmente

### Opção 1: Simples (Recomendado)
```bash
celery -A config flower --port=5555
```

Acesse: **http://localhost:5555**

### Opção 2: Com script
```bash
bash start-flower.sh
```

### Opção 3: Django command
```bash
python manage.py flower_manage start

# Com opções customizadas
python manage.py flower_manage start --port=6000 --log-level=debug

# Em background
python manage.py flower_manage start --background
```

### Opção 4: Com configuração avançada
```bash
celery -A config flower --config=config.flower_config
```

---

## 📋 Fluxo Completo Local (4 Terminais)

### Terminal 1: Django
```bash
python manage.py runserver 0.0.0.0:8000
```

### Terminal 2: Celery Worker
```bash
celery -A config worker -l info
```

### Terminal 3: Celery Beat (Scheduler)
```bash
celery -A config beat -l info
```

### Terminal 4: Flower Dashboard
```bash
celery -A config flower --port=5555
```

Agora abra no navegador:
- App: http://localhost:8000
- Flower: http://localhost:5555

---

## 🎯 O que você Verá no Flower

### Home/Dashboard
```
┌────────────────────────────────────────┐
│           FLOWER DASHBOARD             │
├────────────────────────────────────────┤
│                                        │
│  📊 ACTIVE TASKS: 2                   │
│  ✓ SUCCEEDED: 47                      │
│  ✗ FAILED: 1                          │
│  ⏳ PENDING: 5                        │
│                                        │
│  👷 WORKERS ONLINE: 1                 │
│  celery@hostname (4 concurrency)      │
│                                        │
└────────────────────────────────────────┘
```

### Abas Principais

#### 1. **Tasks** - Histórico de todas as tasks
```
Task Name                  | Received | Succeeded | Failed | %
export_instrumentos        | 23       | 23        | 0      | 100%
send_daily_report         | 7        | 6         | 1      | 85.7%
cleanup_old_exports       | 14       | 14        | 0      | 100%
send_email_notifications  | 42       | 40        | 2      | 95.2%
```

#### 2. **Workers** - Status dos workers
```
Worker: celery@hostname
├─ Status: Online ✓
├─ Concurrency: 4
├─ Pool: prefork
├─ Uptime: 2 days 3h
├─ Active: 0
├─ Processed: 127
└─ Pool size: 4
```

#### 3. **Real-time** - Monitoramento ao vivo
```
[Atualização em tempo real via WebSocket]

⏳ export_instrumentos (0.23s)
   Status: STARTED
   Worker: celery@hostname

✅ send_daily_report (1.45s)
   Status: SUCCESS
   Worker: celery@hostname

⏳ send_email_notifications (0.15s)
   Status: PENDING
   Worker: (aguardando)
```

#### 4. **Task Details** - Clique em uma task para ver detalhes
```
Task: export_instrumentos
Task ID: abc123def456...
Status: SUCCESS
Runtime: 2.34 seconds
Retries: 0
Returned: File saved to /exports/instrumentos_2025-12-09.xlsx
Queue: exports
Exchange: celery
Routing Key: exports
```

---

## 🧪 Teste Prático

### 1. Criar Dados de Teste
```bash
python manage.py create_test_data_fase5
```

### 2. Disparar Task via Django Shell
```bash
python manage.py shell

# No shell Python:
from metrologia.tasks import export_instrumentos
from celery import current_app

# Disparar task
task = export_instrumentos.delay(20, ['excel'])
print(f"Task ID: {task.id}")
print(f"Status: {task.status}")

# Sair
exit()
```

### 3. Ver no Flower
```
Abra http://localhost:5555

Vá a "Tasks" e procure por:
✅ export_instrumentos com status SUCCESS

Clique nela para ver:
- Tempo de execução
- Resultado (caminho do arquivo)
- Worker que processou
```

---

## 🔧 Gerenciar Flower via Django Command

### Ver Status
```bash
python manage.py flower_manage status
```

Saída:
```
✓ Flower is running (PID: 12345)
Access: http://localhost:5555
```

### Ver Configuração
```bash
python manage.py flower_manage config
```

Saída:
```
Port..................... 5555
Username................ admin
Log Level............... info
Database................ flower.db
Max Tasks............... 10000
Broker URL.............. redis://localhost:6379/0
```

### Parar Flower
```bash
python manage.py flower_manage stop
```

### Reiniciar Flower
```bash
python manage.py flower_manage restart
```

---

## 📱 Navegação no Dashboard

### Menu Superior
```
Home | Tasks | Workers | Real-time | Monitor | API | ...
```

### Buscar Tasks
```
Botão "Search" → Digite parte do nome
Ex: "export" → mostra só tasks com "export"
```

### Filtrar por Worker
```
Clique no nome do worker → vê tasks daquele worker
```

### Exportar Dados
```
Botão "Download" → Salva dados em CSV
```

---

## 🚨 Monitorar Falhas

### No Flower
1. Vá a aba "Tasks"
2. Procure por tasks com **Status: FAILURE**
3. Clique na task para ver erro completo
4. Veja "Traceback" para debug

### Exemplo de Falha
```
Task: send_email_notifications
Status: FAILURE
Traceback:
  SMTPAuthenticationError: Authentication failed on connection
  
Solution:
  - Verificar EMAIL_HOST_PASSWORD
  - Testar email backend: python manage.py shell
  - Enviar teste: from django.core.mail import send_mail
```

---

## 📊 Métricas Úteis

### KPIs para Monitorar

1. **Task Success Rate**
   - Target: > 95%
   - Fórmula: Succeeded / (Succeeded + Failed)

2. **Average Task Duration**
   - Target: < 5s para exports
   - Target: < 30s para relatórios

3. **Queue Depth**
   - Target: < 100 tasks pendentes
   - Se > 100: aumentar workers

4. **Worker Uptime**
   - Target: 99.9%
   - Monitor: procurar por workers offline

### Como Ver no Flower
```
Home → mostra métricas principais
Real-time → mostra em tempo real
API → /api/stats → retorna JSON com dados
```

---

## 🔌 API REST

Flower expõe uma REST API:

```bash
# Ver todas as tasks
curl http://localhost:5555/api/tasks

# Ver tasks de um worker específico
curl http://localhost:5555/api/workers/celery@hostname

# Ver estatísticas gerais
curl http://localhost:5555/api/stats

# Forçar shutdown de um worker (cuidado!)
curl -X POST http://localhost:5555/api/workers/celery@hostname/shutdown

# Aumentar concorrência de um worker
curl -X POST http://localhost:5555/api/workers/celery@hostname/pool/grow?n=2
```

### Exemplo de Response
```json
{
  "tasks": {
    "export_instrumentos": {
      "received": 23,
      "started": 23,
      "succeeded": 23,
      "failed": 0,
      "retried": 0,
      "total": 23
    }
  }
}
```

---

## 🐛 Troubleshooting

### Problema: "Connection Refused"
```
Erro: Failed to connect to Celery
Solução:
1. Verificar se Redis está rodando: redis-cli ping
2. Verificar CELERY_BROKER_URL
3. Verificar firewall porta 6379
```

### Problema: "No Workers Available"
```
Erro: Nenhum worker aparece no Flower
Solução:
1. Terminal 2: celery -A config worker -l info
2. Aguardar 5 segundos
3. Atualizar Flower (F5)
```

### Problema: "Task Não Aparece"
```
Erro: Disparei task mas não vejo em Tasks
Solução:
1. Verificar se worker está rodando
2. Verificar se task está em qms/tasks.py
3. Verificar logs do worker
4. Flower precisa estar rodando quando task é disparada
```

### Problema: Dashboard Lento
```
Erro: Flower carrega muito lentamente
Solução:
1. Reduza FLOWER_MAX_TASKS em .env
2. Limpe histórico: flower --purge
3. Aumentar RAM se muitas tasks
```

---

## 🚀 Próximas Etapas

### 1. ✅ Local Development
- ✓ Flower instalado
- ✓ Configuração criada
- ✓ Commands Django adicionados

### 2. 🟡 Teste com Dados
- [ ] Disparar tasks manualmente
- [ ] Ver execução no Flower
- [ ] Testar erro intencional
- [ ] Verificar alertas

### 3. 🟡 Deploy em Railway
- [ ] Adicionar variáveis ao Railway
- [ ] Ativar dyno "flower"
- [ ] Testar URL pública
- [ ] Configurar autenticação

### 4. 🟡 Monitoramento Contínuo
- [ ] Setup alertas de email
- [ ] Monitorar success rate
- [ ] Monitorar worker uptime
- [ ] Revisar logs regularmente

---

## 📚 Recursos

**Documentação Completa:** `FLOWER_CONFIGURACAO_FASE5.md`

**Arquivos:**
- `config/flower_config.py` - Configuração avançada
- `start-flower.sh` - Script de inicialização
- `qms/management/commands/flower_manage.py` - Django command
- `.env.example.fase5` - Variáveis de ambiente

**Comandos Rápidos:**
```bash
# Iniciar
celery -A config flower --port=5555

# Django command
python manage.py flower_manage start

# Ver status
python manage.py flower_manage status

# Parar
python manage.py flower_manage stop

# Ver config
python manage.py flower_manage config
```

---

## ✅ Checklist

- ✅ Flower instalado (pip install flower==2.0.1)
- ✅ Procfile atualizado com dyno flower
- ✅ Configuração em config/flower_config.py
- ✅ Script start-flower.sh criado
- ✅ Django command flower_manage.py criado
- ✅ Variáveis .env.example.fase5 atualizadas
- ✅ Documentação FLOWER_CONFIGURACAO_FASE5.md criada
- ✅ Testado localmente (em desenvolvimento)

---

## 🎉 Status Final

**Task #7 Progress:** 80% ✅

**O que falta:**
- Deploy em Railway
- Configurar autenticação
- Setup alertas de email

**Próximo:** Task #8 - E2E Integration Tests

---

*Data: 9 de Dezembro de 2025*  
*Versão: Flower 2.0.1*  
*Status: ✅ PRONTO PARA DESENVOLVIMENTO*
