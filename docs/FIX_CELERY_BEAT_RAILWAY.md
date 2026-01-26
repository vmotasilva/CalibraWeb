# Fix: Celery Beat Deployment Hung on Railway - Environment Variable Expansion Error

**Data**: 2026-01-07  
**Status**: ✅ FIXED  
**Severity**: 🔴 CRITICAL - Celery Beat não iniciava

---

## Problema Identificado

O Celery Beat ficou travado durante o deploy no Railway com o seguinte erro:

```
[2026-01-07 09:03:22,903: CRITICAL/MainProcess] beat raised exception <class 'ModuleNotFoundError'>: 
ModuleNotFoundError("No module named '${REDIS_URL}'")

Configuration ->
    . broker -> amqp://guest:**@%24%7BREDIS_URL%7D:5672//
```

### Causa Raiz

O arquivo `.env.example` continha:

```dotenv
REDIS_URL=redis://default:password@host:6379/0
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

**O Problema**: A sintaxe `${VARIAVEL}` é uma **expansão de template shell**, NÃO uma variável de ambiente Python.

Quando o Railway carrega o arquivo `.env`, ele trata `${REDIS_URL}` como uma **string literal** em vez de substituir pelo valor real da variável `REDIS_URL`. Como resultado:

- `CELERY_BROKER_URL` recebe o valor literal: `"${REDIS_URL}"`
- Celery tenta importar um módulo chamado `${REDIS_URL}` (inválido!)
- Erro: `ModuleNotFoundError: No module named '${REDIS_URL}'`

---

## Solução Aplicada

### 1️⃣ Corrigir `.env.example`

**Antes:**
```dotenv
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
```

**Depois:**
```dotenv
CELERY_BROKER_URL=redis://default:password@host:6379/0
CELERY_RESULT_BACKEND=redis://default:password@host:6379/0
```

**Arquivo afetado**: [.env.example](.env.example)

### 2️⃣ Verificação do Settings.py (Já Correto ✅)

O `config/settings.py` **já está implementado corretamente**:

```python
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
```

Esta implementação:
- ✅ Tenta carregar `CELERY_BROKER_URL` primeiro
- ✅ Se não existir, tenta `REDIS_URL` 
- ✅ Se nenhuma existir, usa fallback local
- ✅ Usa `os.getenv()` (Python), não template shell

---

## Instruções para Re-Deploy no Railway

### Opção 1: Configurar Variáveis de Ambiente (RECOMENDADO)

No Railway, dentro da aba **"Variables"** do seu serviço, defina **EXPLICITAMENTE**:

```
REDIS_URL=redis://default:PASSWORD@host.railway.app:PORT/0
CELERY_BROKER_URL=redis://default:PASSWORD@host.railway.app:PORT/0
CELERY_RESULT_BACKEND=redis://default:PASSWORD@host.railway.app:PORT/0
```

**Onde obter estas informações:**
1. Acesse o serviço Redis no Railway
2. Copie a URL de conexão da aba "Connect"
3. Cole em cada variável conforme acima

### Opção 2: Usar .env.local no Repository (Se Aplicável)

Se você tem um arquivo `.env` no repositório:

```dotenv
REDIS_URL=redis://default:PASSWORD@host.railway.app:PORT/0
CELERY_BROKER_URL=redis://default:PASSWORD@host.railway.app:PORT/0
CELERY_RESULT_BACKEND=redis://default:PASSWORD@host.railway.app:PORT/0
```

### Opção 3: Deploy Fresh (Mais Seguro)

```bash
# 1. Fazer pull do código corrigido
git pull origin main

# 2. No Railway, redeploy o serviço:
# - Deletar a instância travada (se necessário)
# - Novo deploy com as variáveis corretas
# - Celery Beat iniciará corretamente
```

---

## Checklist de Verificação Pós-Deploy

- [ ] Celery Beat iniciou sem erros
- [ ] Log mostra: `celery beat v5.3.1 (emerald-rush) is starting.`
- [ ] Nenhum `ModuleNotFoundError` ou erro de broker
- [ ] Tarefas agendadas estão sendo executadas
- [ ] Verificar se `CELERY_BROKER_URL` está sendo lido corretamente (não `${REDIS_URL}`)

### Verificar Logs

```bash
# No Railway, visualize os logs do serviço Celery Beat:
# Procure por mensagens de sucesso como:
# "beat: Starting..."
# "Scheduler: Adjusting UTC offset..."
```

---

## Análise Técnica Detalhada

### Por que `${VARIAVEL}` não funciona no Railway?

Railway e a maioria das plataformas cloud carregam variáveis de ambiente de forma literal:

1. **Shell Scripts** (`.sh`): Expandem `${VAR}` para o valor
   ```bash
   export CELERY_BROKER_URL=${REDIS_URL}  # ✅ Expande
   ```

2. **Arquivos .env** (Python): Tratam `${VAR}` como string literal
   ```dotenv
   CELERY_BROKER_URL=${REDIS_URL}  # ❌ Fica literal!
   ```

3. **Railway Variables UI**: Valores são atribuídos diretamente, sem expansão
   - `CELERY_BROKER_URL=redis://...` → lê exatamente este valor
   - `CELERY_BROKER_URL=${REDIS_URL}` → lê a string `"${REDIS_URL}"`

### Celery Broker Error Flow

```
1. Railway carrega: CELERY_BROKER_URL="${REDIS_URL}"
2. Django settings.py lê: CELERY_BROKER_URL="${REDIS_URL}"
3. Celery tenta conectar ao broker: amqp://guest:**@%24%7BREDIS_URL%7D:5672//
4. URL está malformada (contém literal ${REDIS_URL})
5. Celery tenta parsear como backend: symbol_by_name("${REDIS_URL}")
6. Python importlib tenta: import ${REDIS_URL}
7. Erro: ModuleNotFoundError: No module named '${REDIS_URL}'
8. Celery Beat crash!
```

---

## Prevenção Futura

### ✅ Boas Práticas para .env

1. **Nunca use expansão de template** em arquivos `.env`
   ```dotenv
   ❌ CELERY_BROKER_URL=${REDIS_URL}
   ✅ CELERY_BROKER_URL=redis://host:6379/0
   ```

2. **Use valores diretos ou fallback no Python**
   ```python
   # settings.py
   CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", 
                                  os.getenv("REDIS_URL", 
                                           "redis://localhost:6379/0"))
   ```

3. **Para Railway, defina ambas as variáveis explicitamente** quando necessário
   ```
   REDIS_URL=redis://...
   CELERY_BROKER_URL=redis://...
   ```

4. **Documente a configuração**
   - Use `.env.example` com valores finais, não templates
   - Use `.env.railway.example` para instruções específicas do Railway

---

## Arquivos Modificados

| Arquivo | Mudança | Motivo |
|---------|---------|--------|
| `.env.example` | Removeu `${REDIS_URL}` | Sintaxe inválida para .env |
| `config/settings.py` | Nenhuma (já correto) | Lógica de fallback funciona |
| `config/celery.py` | Nenhuma (já correto) | Carrega settings corretamente |

---

## Referências

- [Django Environment Variables](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [Celery Configuration](https://docs.celeryproject.org/en/stable/getting-started/first-steps-with-celery.html)
- [Python-dotenv Documentation](https://python-dotenv.readthedocs.io/)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)

---

**Autoria**: GitHub Copilot  
**Última Atualização**: 2026-01-07 12:04 UTC  
**Status**: Ready for Deployment ✅
