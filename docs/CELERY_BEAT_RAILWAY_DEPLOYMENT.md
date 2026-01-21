# Guia de Deploy: Celery Beat no Railway

**Data**: 2026-01-07  
**Status**: 🔧 EM CONSTRUÇÃO  
**Objetivo**: Configurar Celery Beat como um serviço separado no Railway

---

## Problema Identificado

O deploy do Celery Beat estava falhando porque:

1. ❌ O container estava tentando rodar **Gunicorn** (servidor web HTTP)
2. ❌ O Railway fazia healthcheck em `http://localhost:8000/healthz`
3. ❌ Gunicorn não conseguia iniciar ou responder
4. ❌ Após 337+ tentativas de healthcheck, o deploy foi marcado como falha

**Raiz do problema**: O `entrypoint.py` estava configurado para rodar Gunicorn, não Celery Beat.

---

## Solução Implementada

### 1. Novo Entrypoint para Celery Beat

**Arquivo**: [entrypoint-beat.py](entrypoint-beat.py)

Este script:
- ✅ Inicia o Celery Beat Scheduler
- ✅ Usa o banco de dados como scheduler (persistência)
- ✅ Não expõe portas HTTP
- ✅ Não requer healthcheck HTTP

### 2. Dockerfile Específico para Celery Beat

**Arquivo**: [Dockerfile.beat](Dockerfile.beat)

Diferenças do Dockerfile.web:
- ✅ Não expõe porta 8000 (não é um servidor web)
- ✅ Não define healthcheck HTTP (Celery Beat é um daemon)
- ✅ Entrypoint executa `entrypoint-beat.py` em vez de `entrypoint.py`

### 3. Architecture de Microserviços

Você precisa de 3 serviços separados no Railway:

```
┌─────────────────────────────────────────────────┐
│                Railway Project                   │
├─────────────────────────────────────────────────┤
│                                                   │
│  1. PostgreSQL (Database)                        │
│     ├─ POSTGRES_URL                              │
│     └─ DATABASE_URL                              │
│                                                   │
│  2. Redis (Message Broker)                       │
│     ├─ REDIS_URL                                 │
│     ├─ CELERY_BROKER_URL                         │
│     └─ CELERY_RESULT_BACKEND                     │
│                                                   │
│  3. CalibraWeb (Web Application)                 │
│     ├─ Image: Dockerfile (padrão)                │
│     ├─ PORT: 8000                                │
│     └─ Healthcheck: HTTP /healthz                │
│                                                   │
│  4. Celery Worker (Optional - Async Tasks)       │
│     ├─ Image: Dockerfile.worker (to be created)  │
│     ├─ PORT: none                                │
│     └─ Healthcheck: none                         │
│                                                   │
│  5. Celery Beat (Scheduler - NEW)                │
│     ├─ Image: Dockerfile.beat                    │
│     ├─ PORT: none                                │
│     └─ Healthcheck: none                         │
│                                                   │
└─────────────────────────────────────────────────┘
```

---

## Passo a Passo: Configurar no Railway

### OPÇÃO A: Se você já tem um projeto Railway

#### 1. Deletar o serviço que está falhando

1. Acesse seu projeto no Railway: https://railway.app
2. Clique no serviço que está falhando (o que tenta rodar o Celery Beat)
3. Vá para Settings → Danger Zone
4. Clique em "Delete Service"

#### 2. Criar um novo serviço para Celery Beat

1. Na página do projeto, clique em "+ Create"
2. Selecione "Empty Service"
3. Nome: `celery-beat`
4. Continue

#### 3. Conectar o repositório GitHub

1. Na aba "Deployments", clique em "Connect GitHub"
2. Selecione seu repositório `CalibraWeb`
3. Clique em "Deploy"

#### 4. Configurar o Dockerfile

1. Vá para a aba "Settings"
2. Procure por "Dockerfile"
3. Cole: `Dockerfile.beat`
4. Salve

#### 5. Configurar variáveis de ambiente

1. Vá para a aba "Variables"
2. Adicione as seguintes variáveis (copie do seu serviço PostgreSQL e Redis):

```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=False
SECRET_KEY=[sua-chave-secreta]
ALLOWED_HOSTS=*

# Database
DATABASE_URL=[copie do serviço PostgreSQL]
POSTGRES_URL=[copie do serviço PostgreSQL]

# Redis e Celery
REDIS_URL=[copie do serviço Redis]
CELERY_BROKER_URL=[copie do serviço Redis]
CELERY_RESULT_BACKEND=[copie do serviço Redis]

# Celery Beat Config
CELERY_TIMEZONE=America/Sao_Paulo
```

#### 6. Deploy automático

1. Salve as variáveis
2. Railway detectará a mudança no repositório
3. O deploy iniciará automaticamente
4. Verifique os logs para confirmar que Celery Beat iniciou

---

### OPÇÃO B: Se você quer separar em 2 projetos (Web + Beat)

**Serviço 1 - Web Application**:
- Dockerfile: `Dockerfile` (padrão)
- Entrypoint: `entrypoint.py` (Gunicorn)
- Portas: 8000 (HTTP)
- Healthcheck: Ativado

**Serviço 2 - Celery Beat**:
- Dockerfile: `Dockerfile.beat`
- Entrypoint: `entrypoint-beat.py`
- Portas: Nenhuma
- Healthcheck: Desativado

Ambos compartilham as mesmas variáveis de ambiente (Database, Redis).

---

## Variáveis de Ambiente Necessárias

### Obrigatórias

```env
# Django
DJANGO_SETTINGS_MODULE=config.settings
SECRET_KEY=sua-chave-secreta-super-segura
DEBUG=False
ALLOWED_HOSTS=*

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@host:5432/dbname
POSTGRES_URL=postgresql://user:password@host:5432/dbname

# Redis & Celery
REDIS_URL=redis://default:password@host:6379/0
CELERY_BROKER_URL=redis://default:password@host:6379/0
CELERY_RESULT_BACKEND=redis://default:password@host:6379/0

# Celery Config
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=True
```

### Opcionais (Email, AWS S3, etc.)

```env
# Email (se usar)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app

# AWS S3 (se usar para media)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
```

---

## Verificação Pós-Deploy

### 1. Confirmar que Celery Beat iniciou

Verifique os logs do serviço:

```
[CELERY_BEAT_ENTRYPOINT] ✓ Celery version: 5.3.1
[CELERY_BEAT_ENTRYPOINT] ✓ Django version: 5.0.14
[CELERY_BEAT_ENTRYPOINT] Starting Celery Beat Scheduler...
```

### 2. Confirmar que as tarefas estão agendadas

Os logs devem mostrar:

```
beat: Scheduler: celery.beat.PersistentScheduler
beat: Initializing schedule database...
beat: Entering tick loop.
```

### 3. Verificar tarefas agendadas (no Django Admin)

1. Acesse o site web: https://seu-site.railway.app
2. Vá para `/admin/django_celery_beat/` (se django-celery-beat estiver instalado)
3. Verifique as tarefas na seção "Periodic Tasks"

---

## Tarefas Agendadas Configuradas

As seguintes tarefas estão agendadas em [qms/celery_beat_config.py](qms/celery_beat_config.py):

| Tarefa | Schedule | Descrição |
|--------|----------|-----------|
| `relatorio-diario-vencidos` | 08:00 AM | Relatório diário de instrumentos vencidos |
| `relatorio-semanal-estatisticas` | Seg 09:00 AM | Estatísticas semanais |
| `alerta-critico-vencidos` | A cada 4h | Alertas críticos |
| `warm-instrumentos-cache` | A cada 25 min | Cache warming de instrumentos |
| `warm-statistics-cache` | A cada 55 min | Cache warming de estatísticas |
| `warm-categories-cache` | A cada 55 min | Cache warming de categorias |

---

## Troubleshooting

### Problema: "ModuleNotFoundError: No module named '${REDIS_URL}'"

**Solução**: Verifique se as variáveis estão definidas **corretamente** no Railway:
- NÃO use `${REDIS_URL}` na variável CELERY_BROKER_URL
- Copie a URL completa do Redis (ex: `redis://default:password@host:6379/0`)

### Problema: "ConnectionError: Error 111 connecting to Redis"

**Solução**: 
- Verifique se o serviço Redis está rodando
- Confirme que a REDIS_URL está correta
- Teste a conexão manualmente com `redis-cli`

### Problema: Database Migration Error

**Solução**:
- Se for a primeira vez, o Celery Beat precisa das migrações:
  ```bash
  python manage.py migrate
  ```
- No Railway, você pode fazer isso adicionando um comando pré-deploy:
  1. Settings → Pre-Deploy Checks
  2. Execute: `python manage.py migrate`

### Problema: Tarefas não estão sendo executadas

**Verificação**:
1. Confirme que Celery Beat está rodando (verifique logs)
2. Confirme que há workers rodando (Celery Worker service)
3. Verifique se as tarefas estão definidas em `qms/celery_beat_config.py`

---

## Próximos Passos

- [ ] Criar `Dockerfile.worker` para Celery Workers (processamento de tarefas)
- [ ] Implementar retry logic para tarefas
- [ ] Monitorar execução de tarefas com Flower
- [ ] Configurar alertas de falhas

---

## Referências

- [Celery Documentation](https://docs.celeryproject.org/)
- [Railway Documentation](https://docs.railway.app/)
- [Django Celery Beat](https://github.com/celery/django-celery-beat)
