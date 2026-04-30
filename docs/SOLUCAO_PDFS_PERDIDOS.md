# 🔧 SOLUÇÃO: PDFs Não Encontrados em Produção (Railway)

## 🚨 PROBLEMA IDENTIFICADO

Os arquivos PDF que são carregados no Railway estão desaparecendo. **Causa raiz**: 

Os PDFs são salvos em `/app/media/` que é um **diretório efêmero** do container Docker no Railway. Quando o container é reiniciado (automático no Railway), todos os arquivos são perdidos.

---

## ❌ CONFIGURAÇÃO ATUAL (PROBLEMA)

```python
# config/settings.py - Linha ~250
MEDIA_ROOT = BASE_DIR / "media"  # /app/media/ no Railway
MEDIA_URL = "/media/"
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
```

**Problema**: Este storage é **temporário no Railway** e é perdido quando o dyno reinicia.

---

## ✅ SOLUÇÃO: CONFIGURAR VOLUME PERSISTENTE NO RAILWAY

### 1️⃣ PASSO 1: Criar Volume no Railway

No painel do Railway:

1. Acesse seu projeto `CalibraWeb`
2. Vá em **Settings** → **Environment**
3. Procure por **Volumes**
4. Clique em **+ Create Volume**
5. Configure:
   - **Mount Path**: `/data/media`
   - **Size**: 10GB (inicial, pode aumentar depois)

### 2️⃣ PASSO 2: Atualizar settings.py

Modifique `config/settings.py`:

```python
import os
from pathlib import Path

# ... código anterior ...

# Media files (PDFs, certificados, etc)
PERSIST_MEDIA_PATH = os.environ.get('PERSIST_MEDIA_PATH', '/data/media')

if os.environ.get('USE_S3'):
    # Opção 1: Usar AWS S3 (mais recomendado para produção)
    INSTALLED_APPS.append('storages')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_ROOT = None  # S3 não usa MEDIA_ROOT local

elif PERSIST_MEDIA_PATH and PERSIST_MEDIA_PATH != '/data/media':
    # Opção 2: Usar volume persistente do Railway
    MEDIA_ROOT = Path(PERSIST_MEDIA_PATH)
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    
else:
    # Opção 3: Fallback para desenvolvimento
    MEDIA_ROOT = BASE_DIR / "media"
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Configure MEDIA_URL
MEDIA_URL = "/media/"
```

### 3️⃣ PASSO 3: Atualizar railway.toml

Crie ou atualize `railway.toml` na raiz do projeto:

```toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "python manage.py collectstatic --noinput && python manage.py migrate && gunicorn config.wsgi:application"

[[services.web.mounts]]
path = "/data/media"
volume = "media_storage"
```

### 4️⃣ PASSO 4: Adicionar Variáveis de Ambiente no Railway

No painel do Railway, adicione:

```
PERSIST_MEDIA_PATH=/data/media
```

### 5️⃣ PASSO 5: Fazer Commit e Push

```bash
cd c:\CalibraWeb
git add config/settings.py railway.toml
git commit -m "Configure persistent storage for media files on Railway"
git push origin main
```

---

## 🎯 ALTERNATIVA: Usar AWS S3 (Recomendado)

Se preferir usar S3 em vez de volume local:

### 1. Criar bucket S3 na AWS
```bash
# Ou via AWS Console:
# S3 → Create Bucket → "calibraweb-media"
# Bloquear acesso público
# Habilitar versioning
```

### 2. Criar credenciais IAM
```bash
# AWS Console → IAM → Users → Create User
# Adicionar policy: AmazonS3FullAccess
# Copiar Access Key ID e Secret Access Key
```

### 3. Configurar variáveis no Railway
```
USE_S3=True
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_STORAGE_BUCKET_NAME=calibraweb-media
AWS_S3_REGION_NAME=us-east-1
```

### 4. Instalar biblioteca S3
```bash
pip install boto3 django-storages
```

---

## 🔄 RECUPERAR PDFs ANTIGOS

Se havia PDFs perdidos, você pode:

1. **Verificar backup local**
   ```bash
   # Se você tem um backup do banco de dados
   python manage.py dumpdata metrologia.HistoricoCalibracao > backup_historico.json
   ```

2. **Re-fazer upload dos certificados**
   - Ir em cada histórico de calibração
   - Anexar novamente o PDF do certificado
   - Os novos arquivos serão salvos no volume persistente

3. **Migrar de cópia local (se houver)**
   ```bash
   # No Railway (via SSH ou Django shell)
   python manage.py shell
   
   # Copiar arquivos do /app/media para /data/media
   import shutil
   import os
   shutil.copytree('/app/media', '/data/media', dirs_exist_ok=True)
   ```

---

## ✅ VERIFICAÇÃO

Após fazer deploy:

1. **Acessar a aplicação**
   ```
   https://calibraweb.up.railway.app
   ```

2. **Fazer upload de um PDF de teste**
   - Ir em um histórico de calibração
   - Anexar um certificado PDF
   - Verificar se aparece na listagem

3. **Reiniciar o container** (simular problema original)
   - No Railway Dashboard → Project Settings → Restart
   - Voltar à aplicação
   - **PDF deve estar acessível** (não foi perdido!)

4. **Verificar logs**
   ```bash
   railway logs  # ou via web UI
   ```

   Procurar por:
   ```
   ✅ Usando volume persistente em: /data/media
   ```

---

## 📊 COMPARAÇÃO DE SOLUÇÕES

| Solução | Pros | Contras |
|---------|------|---------|
| **Volume Local** | Simples, grátis | Limitado a um container, precisa rebalancear |
| **S3** | Escalável, multi-region | Custo mensal, configuração inicial |
| **PostgreSQL Blob** | Backup automático | Lento para arquivos grandes |
| **Azure Blob** | Integrado com Azure | Custo, vendor lock-in |

**Recomendação**: Para MVP: **Volume Local**. Para produção escalonada: **S3**.

---

## 🆘 TROUBLESHOOTING

### PDFs ainda não aparecem após restart?

1. **Verificar mount path**
   ```bash
   railway exec ls -la /data/media/
   ```

2. **Verificar permissões**
   ```bash
   railway exec chmod -R 755 /data/media/
   ```

3. **Verificar configuração Django**
   ```bash
   railway exec python manage.py shell
   >>> from django.conf import settings
   >>> print(settings.MEDIA_ROOT)
   /data/media
   >>> print(settings.DEFAULT_FILE_STORAGE)
   django.core.files.storage.FileSystemStorage
   ```

4. **Ver logs**
   ```bash
   railway logs --follow
   ```

### Erro: "Mount path conflicts with container filesystem"

- O path `/data/media` já estava em uso
- Tente: `/persistent/media` ou `/app/persistent/media`

### Erro: "Volume size exceeded"

- Arquivos ocupam mais do que o tamanho alocado
- Aumentar tamanho do volume no Railway Dashboard
- Ou limpar arquivos antigos

---

## 📝 PRÓXIMOS PASSOS

1. ✅ Implementar uma das soluções acima
2. ✅ Fazer deploy para o Railway
3. ✅ Testar com upload e restart
4. ✅ Configurar backup automático dos PDFs (via cron job)
5. ✅ Monitorar uso de espaço em disco

