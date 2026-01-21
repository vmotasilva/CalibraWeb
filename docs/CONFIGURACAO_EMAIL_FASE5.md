# -*- coding: utf-8 -*-
"""
CONFIGURAÇÃO DE EMAIL PARA FASE 5 - Relatórios e Alertas

IMPORTANTE: Adicione estas configurações ao seu settings.py

OPÇÃO 1: Gmail (Recomendado para desenvolvimento)
========================================
```python
# Email Configuration for Gmail
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'seu-email@gmail.com'
EMAIL_HOST_PASSWORD = 'sua-app-password'  # Não usar senha normal!
DEFAULT_FROM_EMAIL = 'seu-email@gmail.com'

# Destinatários para tarefas agendadas
REPORT_EMAIL_TO = ['gestor@empresa.com', 'supervisor@empresa.com']
ALERT_EMAIL_TO = ['gestor@empresa.com', 'supervisor@empresa.com']
MAINTENANCE_EMAIL = 'manutencao@empresa.com'
```

OPÇÃO 2: SendGrid
==================
```python
EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
SENDGRID_API_KEY = 'seu-chave-sendgrid'
DEFAULT_FROM_EMAIL = 'noreply@empresa.com'
```

OPÇÃO 3: AWS SES
================
```python
EMAIL_BACKEND = 'django_ses.SESBackend'
AWS_SES_REGION_NAME = 'us-east-1'
AWS_SES_REGION_ENDPOINT = 'email.us-east-1.amazonaws.com'
AWS_ACCESS_KEY_ID = 'sua-key'
AWS_SECRET_ACCESS_KEY = 'sua-secret'
DEFAULT_FROM_EMAIL = 'noreply@empresa.com'
```

OPÇÃO 4: desenvolvimento local (Console Backend)
=================================================
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# Emails são exibidos no console, sem enviar realmente
```

PRÓXIMOS PASSOS:
================
1. Escolha uma das opções acima
2. Adicione ao seu config/settings.py
3. Instale a biblioteca necessária se não tiver
4. Configure as credenciais
5. Teste com: python manage.py shell
   >>> from django.core.mail import send_mail
   >>> send_mail('Test', 'Body', 'from@example.com', ['to@example.com'])

IMPORTANTE - Gmail:
====================
- Não use sua senha normal do Gmail
- Crie uma "Senha de app" em: https://myaccount.google.com/apppasswords
- Ative a "Autenticação em duas etapas" primeiro
- Use a senha de app gerada de 16 caracteres

CONFIGURAÇÃO DE DESTINATÁRIOS (Settings):
===========================================
```python
# Você também pode usar variáveis de ambiente
import os

REPORT_EMAIL_TO = os.getenv('REPORT_EMAIL_TO', 'gestor@empresa.com').split(',')
ALERT_EMAIL_TO = os.getenv('ALERT_EMAIL_TO', 'supervisor@empresa.com').split(',')
```

VARIÁVEIS DE AMBIENTE RECOMENDADAS:
===================================
```bash
# .env file
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-app-password
REPORT_EMAIL_TO=gestor@empresa.com,supervisor@empresa.com
ALERT_EMAIL_TO=gestor@empresa.com
MAINTENANCE_EMAIL=manutencao@empresa.com
```

TESTE DAS TAREFAS:
==================
```bash
# Teste da tarefa de vencidos
celery -A config call qms.tasks.gerar_relatorio_diario_vencidos

# Teste da tarefa de estatísticas
celery -A config call qms.tasks.gerar_relatorio_semanal_estatisticas

# Teste do alerta crítico
celery -A config call qms.tasks.gerar_relatorio_alerta_critico

# Ou via Django shell
python manage.py shell
>>> from qms.tasks import gerar_relatorio_diario_vencidos
>>> gerar_relatorio_diario_vencidos.delay()
```

MONITORAMENTO:
==============
```bash
# Terminal 1: Worker
celery -A config worker -l info

# Terminal 2: Beat scheduler
celery -A config beat -l info

# Terminal 3: Flower (interface web)
celery -A config flower
# Acesse: http://localhost:5555
```
