# 🚀 QUICK START - FASE 5

## Setup em 5 Minutos

### 1️⃣ Instalar Dependências
```bash
pip install openpyxl reportlab celery
```

### 2️⃣ Configurar Email (escolha uma opção)

**Opção A: Gmail (mais fácil)**
1. Ativar 2FA em https://myaccount.google.com/security
2. Criar "Senha de app" em https://myaccount.google.com/apppasswords
3. Adicionar ao `.env` ou `config/settings.py`:
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'seu-email@gmail.com'
EMAIL_HOST_PASSWORD = 'senha-app-16-chars'
DEFAULT_FROM_EMAIL = 'seu-email@gmail.com'

REPORT_EMAIL_TO = ['gestor@empresa.com']
ALERT_EMAIL_TO = ['supervisor@empresa.com']
```

**Opção B: Console (teste local)**
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### 3️⃣ Integrar Celery Beat

**Em `config/celery.py`, adicione:**
```python
from celery.schedules import crontab
from qms.celery_beat_config import CELERY_BEAT_SCHEDULE, CELERY_QUEUES, CELERY_ROUTES

app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
app.conf.task_queues = CELERY_QUEUES
app.conf.task_routes = CELERY_ROUTES
```

### 4️⃣ Testar Exportações

**Via UI:**
- Dashboard → Metrologia → Instrumentos → Botão "Exportar"
- Escolher Excel/CSV/PDF

**Via URL (exemplos):**
```
http://localhost:8000/metrologia/instrumentos/exportar/?status=vencido&formato=excel
http://localhost:8000/metrologia/estatisticas/exportar/?formato=pdf
http://localhost:8000/metrologia/vencidos/?formato=excel
```

### 5️⃣ Testar Tarefas Agendadas

**Terminal 1 - Worker:**
```bash
celery -A config worker -l info
```

**Terminal 2 - Beat (Scheduler):**
```bash
celery -A config beat -l info
```

**Terminal 3 - Disparar manual:**
```bash
python manage.py shell
>>> from qms.tasks import gerar_relatorio_diario_vencidos
>>> gerar_relatorio_diario_vencidos.delay()
```

**Terminal 4 - Monitor web (opcional):**
```bash
celery -A config flower
# Acesse: http://localhost:5555
```

## ⚡ Atalhos Úteis

### Rodar todos os testes Fase 5
```bash
python manage.py test qms.tests_fase5 -v 2
```

### Testar email antes de configurar Beat
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Body', 'from@example.com', ['to@example.com'])
```

### Ver agendamentos registrados
```bash
python manage.py shell
>>> from qms.celery_beat_config import CELERY_BEAT_SCHEDULE
>>> for name, config in CELERY_BEAT_SCHEDULE.items():
...     print(f"{name}: {config['schedule']}")
```

### Listar tarefas disponíveis
```bash
celery -A config inspect active_queues
celery -A config inspect registered
```

## 📋 Checklist de Deploy

- [ ] Dependências instaladas (openpyxl, reportlab, celery)
- [ ] Email backend configurado (Gmail, SendGrid, ou outra)
- [ ] Variáveis de ambiente setadas
- [ ] Celery Beat importado em config/celery.py
- [ ] Testes Fase 5 passando
- [ ] Worker rodando em background
- [ ] Beat scheduler rodando em background
- [ ] Email testado com `send_mail()`
- [ ] Exportações testadas via UI
- [ ] Tarefas executadas manualmente com sucesso

## 🔗 Arquivos Principais

| Arquivo | Propósito |
|---------|-----------|
| `metrologia/exportadores.py` | Classes de export (Excel, CSV, PDF) |
| `qms/views.py` | 3 novas views de export |
| `qms/urls.py` | 3 novas rotas |
| `qms/tasks.py` | 3 tarefas Celery agendadas |
| `qms/celery_beat_config.py` | Configuração Beat |
| `qms/tests_fase5.py` | 13 testes unitários |

## 🆘 Problemas Comuns

**"Module 'openpyxl' not found"**
```bash
pip install openpyxl
```

**"celery: command not found"**
```bash
pip install celery
```

**"Email não enviando"**
1. Testar com `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'`
2. Verificar credenciais
3. Verificar firewall (porta 587 para Gmail)

**"Beat não agendando"**
1. Verificar se `app.conf.beat_schedule` está setado
2. Rodar com `-l debug`: `celery -A config beat -l debug`
3. Verificar imports em `config/celery.py`

## 📞 Contato & Suporte

Para dúvidas sobre Fase 5:
1. Consultar `FASE_5_DOCUMENTACAO.md`
2. Ver `CONFIGURACAO_EMAIL_FASE5.md`
3. Executar testes: `python manage.py test qms.tests_fase5 -v 2`
