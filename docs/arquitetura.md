# Arquitetura - CalibraWEB

## Estrutura do Projeto

```
CalibraWeb/
├── config/              # Configurações Django (settings, wsgi, asgi)
├── core/                # App principal do projeto
├── metrologia/          # App de metrologia
├── rh/                  # App de recursos humanos
├── organization/        # App de organização
├── procedures/          # App de procedimentos
├── training/            # App de treinamentos
├── shared/              # Utilitários compartilhados
├── scripts/             # Scripts auxiliares
├── docs/                # Documentação
├── manage.py            # Gerenciador Django
├── vercel.json          # Configuração de deploy
└── requirements.txt     # Dependências Python
```

## Stack Tecnológico

- **Framework**: Django 5.0
- **Banco de Dados**: Neon PostgreSQL (produção) / SQLite (desenvolvimento)
- **Cache**: Redis
- **Fila de Mensagens**: Celery
- **Scheduler**: Celery Beat
- **Servidor Web**: Gunicorn
- **Frontend**: Bootstrap 5 + Django Templates
- **Armazenamento**: AWS S3 (produção)

## Fluxo de Deploy

1. Vercel detecta push no Git
2. Instala dependências: `pip install -r requirements.txt`
3. Coleta arquivos estáticos: `python manage.py collectstatic --noinput`
4. Executa migrações: `python manage.py migrate`
5. Expõe a aplicação Django via `config/wsgi.py`

## Arquivos Críticos (NÃO MOVER)

- `manage.py` - Entry point Django
- `config/wsgi.py` - WSGI application
- `vercel.json` - Definição de deploy
- `requirements.txt` - Dependências
- `start.sh`, `start-worker.sh`, `start-beat.sh` - Scripts de inicialização

## Comunicação entre Componentes

```
User (Browser)
    ↓
Nginx (Proxy)
    ↓
Gunicorn (Web)
    ↓
Django Application
    ├→ Database (PostgreSQL)
    ├→ Cache (Redis)
    └→ Celery Queue
        ├→ Worker (Background Jobs)
        └→ Beat (Scheduled Tasks)
```

## Mais Informações

- [Setup Local](./setup.md)
- [Fluxos de Negócio](./fluxos.md)
