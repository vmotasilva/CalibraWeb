# 🔧 Railway - Celery Beat Configuration (FIXED)

## O que foi corrigido

1. ✅ `config/settings.py` - Agora constrói `CELERY_BROKER_URL` a partir de componentes (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD) ou REDIS_URL
2. ✅ `config/celery.py` - Adicionado debug completo e validação robusta
3. ✅ `entrypoint-beat-debug.sh` - Script de inicialização que valida tudo antes de iniciar
4. ✅ `Dockerfile` - Agora executa o script com debug

---

## 📋 Variáveis de Ambiente Necessárias

Adicione **TODAS** essas variáveis no serviço **beat** do Railway:

```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=false
ALLOWED_HOSTS=*.railway.app,localhost
SECRET_KEY=<copie do serviço web>
DATABASE_URL=<copie do PostgreSQL>
REDIS_HOST=<do Redis - veja abaixo>
REDIS_PORT=<do Redis - veja abaixo>
REDIS_PASSWORD=<do Redis - veja abaixo>
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=true
```

---

## 🔍 Como obter as variáveis do Redis (Railway)

### Opção 1: Use a REDIS_URL direta (RECOMENDADO)

Se Railway fornece uma variável `REDIS_URL` completa:
```
REDIS_URL=redis://default:PASSWORD@HOST:PORT/0
```

**Então você SÓ precisa adicionar:**
```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=false
SECRET_KEY=<do web>
DATABASE_URL=<do PostgreSQL>
REDIS_URL=<copie aqui>
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=true
```

### Opção 2: Use componentes individuais (alternativa)

Se Railway dá `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` separados:

```
DJANGO_SETTINGS_MODULE=config.settings
DEBUG=false
SECRET_KEY=<do web>
DATABASE_URL=<do PostgreSQL>
REDIS_HOST=redis-host-123.railway.app
REDIS_PORT=6379
REDIS_PASSWORD=sua_password_aqui
CELERY_TIMEZONE=America/Sao_Paulo
CELERY_ENABLE_UTC=true
```

---

## 🚀 Passo-a-Passo (Railway Dashboard)

1. **Vá para seu projeto CalibraWeb**

2. **Clique no serviço `beat`** (não web, não worker)

3. **Clique na aba `Variables`**

4. **Copie do serviço `web`:**
   - Clique em `web` > `Variables`
   - Copie: `SECRET_KEY`
   - Copie: `ALLOWED_HOSTS`

5. **Copie do banco de dados:**
   - Clique em `PostgreSQL` > `Variables`
   - Copie: `DATABASE_URL`

6. **Copie do Redis:**
   - Clique em `Redis` > `Variables`
   - Copie: `REDIS_URL` OU (`REDIS_HOST` + `REDIS_PORT` + `REDIS_PASSWORD`)

7. **No serviço `beat`, adicione TODAS as variáveis acima**

8. **Clique `Save`**

9. **Railway fará redeploy automaticamente**

---

## ✅ Verificação

Depois de salvar, vá para o serviço `beat`:

1. Clique na aba **`Logs`**
2. Aguarde ~30 segundos
3. Procure por:

```
✅ Django settings loaded for Celery
✅ Database OK
✅ Redis Connection OK
✅ Celery Beat scheduled with X tasks
Entering tick loop
```

Se vir esses sinais = **FUNCIONANDO! ✅**

---

## 🔴 Se ainda não funcionar

Se ainda der erro, colete o log completo:

1. Vá em `beat` > `Logs`
2. Copie TUDO o que aparece
3. Procure por um desses erros:

| Erro | Causa | Solução |
|------|-------|---------|
| `ValueError: Port could not be cast to integer` | REDIS_PORT não é número | Verifique se REDIS_PORT está como número (ex: `6379`) |
| `Connection refused` | Redis não está acessível | Verifique se serviço Redis está `Running` |
| `ModuleNotFoundError` | Django settings não carregou | Verifique se DATABASE_URL é válida |
| `Timeout` | Conexão lenta | Aguarde mais tempo ou redeploie |

---

## 📝 Resumo das Mudanças no Código

- `config/settings.py`: Função `_build_redis_url()` constrói URL robustamente
- `config/celery.py`: Debug detalhado com `_debug_env()`
- `entrypoint-beat-debug.sh`: Script de inicialização que valida tudo
- `Dockerfile`: Permissão para executar novo entrypoint

Tudo foi testado para garantir que:
1. Variáveis de ambiente são expandidas corretamente
2. Redis é detectado automaticamente
3. Banco de dados é validado
4. Celery Beat inicia com segurança
