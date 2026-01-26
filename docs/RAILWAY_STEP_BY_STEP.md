# RAILWAY DEPLOYMENT STEP-BY-STEP (COM SCREENSHOTS)

## ⚠️ IMPORTANTE: Você já tem um projeto Railway com esses serviços?

```
[Existente]          [Novo]
├─ PostgreSQL        
├─ Redis             
├─ CalibraWeb Web    
└─ (Falho) ──────→ Deletar + Criar "celery-beat"
```

---

## PASSO 1: ACESSAR RAILWAY

1. Abra: https://railway.app
2. Faça login com GitHub
3. Clique em seu projeto "CalibraWeb"

```
┌─────────────────────────────────────┐
│ My Projects                         │
├─────────────────────────────────────┤
│ CalibraWeb          📊 $2.50/month  │
│ ├─ PostgreSQL       ✓ UP            │
│ ├─ Redis            ✓ UP            │
│ ├─ CalibraWeb       ✓ UP            │
│ └─ [FAILING]        ✗ FAILED        │
└─────────────────────────────────────┘
```

---

## PASSO 2: DELETAR SERVIÇO FALHO

1. Clique no serviço que está em FAILED (provavelmente o Celery Beat antigo)
2. Clique em "Settings" (engrenagem)
3. Role para baixo até "Danger Zone"
4. Clique em "Delete Service"
5. Confirme digitando o nome

```
Serviço [FAILING] → Settings → Danger Zone → Delete Service
```

---

## PASSO 3: CRIAR NOVO SERVIÇO

Na página do projeto:

1. Clique em "+ New" ou "+ Create"
2. Selecione "GitHub"

```
┌──────────────────────────────────────┐
│ Select Service Type                  │
├──────────────────────────────────────┤
│ ☐ Database                           │
│ ☐ Redis                              │
│ ☑ GitHub                             │ ← Clique aqui
│ ☐ Docker Image                       │
│ ☐ Empty Service                      │
└──────────────────────────────────────┘
```

---

## PASSO 4: SELECIONAR REPOSITÓRIO

1. Autorize o GitHub se pedir
2. Procure por "CalibraWeb"
3. Clique em "vmotasilva/CalibraWeb"
4. Selecione branch "main"
5. Clique em "Deploy"

```
┌──────────────────────────────────────┐
│ Select Repository                    │
├──────────────────────────────────────┤
│ 🔍 vmotasilva/CalibraWeb             │
│                                      │
│ Branch: [main ▼]                    │
│                                      │
│ [ Cancel ]  [ Deploy ]               │
└──────────────────────────────────────┘
```

---

## PASSO 5: NOMEAR O SERVIÇO (IMPORTANTE!)

Você pode ter a opção de nomear o serviço. Se sim:

```
Nome do Serviço: celery-beat
```

Clique em "Deploy"

---

## PASSO 6: AGUARDAR BUILD

Você verá uma tela de build. Aguarde até que mostre:

```
Build Progress:
[████████████████████████████] 100%

Service: celery-beat
Status: Building...
```

Isto pode levar 2-5 minutos. Não feche a página.

---

## PASSO 7: CONFIGURAR DOCKERFILE

Quando o build terminar (ou durante), você precisa trocar o Dockerfile:

1. Clique em "Settings" (engrenagem no topo)
2. Role para "Build"
3. Procure por "Dockerfile"

```
┌──────────────────────────────────────┐
│ Build Settings                       │
├──────────────────────────────────────┤
│ Dockerfile                           │
│ [Dockerfile.beat          ] ← Mude pra isso
│                                      │
│ [ Save ]                             │
└──────────────────────────────────────┘
```

4. Limpe o campo e digite: `Dockerfile.beat`
5. Clique em "Save"
6. Railway iniciará novo build automaticamente

---

## PASSO 8: CONFIGURAR VARIÁVEIS DE AMBIENTE

Você precisa adicionar as variáveis. **IMPORTANTE**: NÃO use templates tipo `${REDIS_URL}`!

### 8.1 Copiar URLs do PostgreSQL e Redis

**Para PostgreSQL:**
1. Clique no serviço "PostgreSQL"
2. Vá para aba "Connect"
3. Procure por "DATABASE_URL" ou "PostgreSQL"
4. Clique no ícone de copiar (📋)
5. Guarde essa URL em algum lugar

Você verá algo como:
```
postgresql://postgres:dajksdhj@railway.railway.internal:5432/railway
```

**Para Redis:**
1. Clique no serviço "Redis"
2. Vá para aba "Connect"
3. Procure por "REDIS_URL" ou "Redis"
4. Clique no ícone de copiar (📋)
5. Guarde essa URL em algum lugar

Você verá algo como:
```
redis://default:zxcvbnm@redis.railway.internal:6379
```

### 8.2 Voltar para celery-beat e adicionar variáveis

1. Clique no serviço "celery-beat"
2. Clique em "Variables" (ou "Environment")

```
┌──────────────────────────────────────┐
│ celery-beat                          │
├─ Overview                           │
├─ Deploy                              │
├─ Settings                            │
└─ Variables ← Clique aqui             │
```

3. Você verá um formulário. Adicione as seguintes variáveis:

```
VARIÁVEL NAME                    | VALOR
─────────────────────────────────────────────────────────────
DJANGO_SETTINGS_MODULE           | config.settings
DEBUG                            | False
SECRET_KEY                       | [copie do serviço web]
ALLOWED_HOSTS                    | *
DATABASE_URL                     | postgresql://postgres:dajksdhj@...
POSTGRES_URL                     | postgresql://postgres:dajksdhj@...
REDIS_URL                        | redis://default:zxcvbnm@...
CELERY_BROKER_URL                | redis://default:zxcvbnm@...
CELERY_RESULT_BACKEND            | redis://default:zxcvbnm@...
CELERY_TIMEZONE                  | America/Sao_Paulo
CELERY_ENABLE_UTC                | True
```

**Para cada variável:**

```
Clique em "New Variable"
                    ↓
┌──────────────────────────────────────┐
│ Name: [DJANGO_SETTINGS_MODULE      ] │
│ Value: [config.settings            ] │
│ [ Add ]                              │
└──────────────────────────────────────┘
```

4. Clique em "Add" após cada uma
5. Quando terminar, clique em "Save" ou "Apply"

---

## PASSO 9: TRIGGER NOVO DEPLOY

Depois que as variáveis forem salvas, Railway fará um novo deploy automaticamente.

Você verá:
```
Deployment in progress...
[████████░░░░░░░░░░░░░░] 50%
```

Aguarde até 100%.

---

## PASSO 10: VERIFICAR LOGS

1. Quando o deploy completar, clique em "Logs"
2. Procure por estas mensagens de **SUCESSO**:

```
[CELERY_BEAT_ENTRYPOINT] ✓ Celery version: 5.3.1
[CELERY_BEAT_ENTRYPOINT] ✓ Django version: 5.0.14
[CELERY_BEAT_ENTRYPOINT] Starting Celery Beat Scheduler...
beat: Scheduler: celery.beat.PersistentScheduler
beat: Entering tick loop.
```

Se ver essas mensagens: **✅ DEU CERTO!**

---

## PASSO 11: TESTAR

1. Acesse seu site: https://seu-site-celery-beat.railway.app
   - Se redirecionou ou deu erro: normal (não é um servidor web)
2. Acesse o web app: https://seu-site-web.railway.app
3. Vá para `/admin/django_celery_beat/`
4. Você deve ver as tarefas agendadas

---

## ⚠️ SE DEU ERRO

### Erro 1: "ModuleNotFoundError: No module named '${REDIS_URL}'"

**Solução**:
1. Clique em "Variables"
2. Procure por CELERY_BROKER_URL
3. Se o valor é `${REDIS_URL}`, está **ERRADO**
4. Copie a URL REAL do Redis (do Connect → REDIS_URL)
5. Cole como: `redis://default:zxcvbnm@redis.railway.internal:6379`
6. Salve e faça novo deploy

### Erro 2: "ConnectionError connecting to Redis"

**Solução**:
1. Confirme que serviço Redis está UP (verde) no painel
2. Confirme que REDIS_URL está correta
3. Tente copiar novamente do Connect tab do Redis

### Erro 3: Deployment falhou durante build

**Solução**:
1. Clique em "Deployments"
2. Veja qual deploy falhou
3. Clique nele para ver o erro completo
4. Procure por mensagens de erro (syntax, imports, etc)

---

## ✅ SUCESSO!

Se você vir:

```
SERVICE: celery-beat
STATUS: UP ✓
DEPLOYMENT: SUCCESS ✓
LOGS: "beat: Entering tick loop" ✓
```

Parabéns! 🎉 Seu Celery Beat está rodando no Railway!

---

## RESUMO DOS PASSOS

```
1. Railway.app → Projeto CalibraWeb
2. Clique no serviço falho → Delete
3. "+ Create" → GitHub → vmotasilva/CalibraWeb → main
4. Settings → Dockerfile: Dockerfile.beat
5. Variables → Copie as 11 variáveis (com URLs reais)
6. Aguarde build (100%)
7. Logs → Procure por "Entering tick loop"
8. Done! ✅
```

---

## TEMPO ESTIMADO

- Copiar URLs: 2 min
- Criar serviço: 3 min
- Configurar variáveis: 5 min
- Deploy/Build: 5 min
- Verificação: 2 min
- **Total: ~17 minutos**

---

## DÚVIDAS?

- Leia: [RAILWAY_VARIABLES_EXAMPLE.md](RAILWAY_VARIABLES_EXAMPLE.md)
- Leia: [CELERY_BEAT_RAILWAY_DEPLOYMENT.md](CELERY_BEAT_RAILWAY_DEPLOYMENT.md)
- Verifique os logs do Railway
