# Configuração de Armazenamento de Mídia - CalibraWeb

## Problema
Em produção no Railway, os arquivos (certificados, padrões) são perdidos quando o container reinicia porque são armazenados em um volume efêmero.

## Solução Implementada

O Django foi configurado com suporte a três backends de armazenamento em ordem de prioridade:

### 1. **AWS S3 (Recomendado para Produção)**
Mais confiável e escalável. Os arquivos ficam armazenados permanentemente na AWS.

**Configuração via variáveis de ambiente:**
```bash
USE_S3=True
AWS_ACCESS_KEY_ID=seu_access_key
AWS_SECRET_ACCESS_KEY=seu_secret_key
AWS_STORAGE_BUCKET_NAME=seu_bucket_name
AWS_S3_REGION_NAME=us-east-1  # opcional
```

**Passos:**
1. Criar um bucket S3 na AWS
2. Criar um usuário IAM com permissões de acesso ao bucket
3. Adicionar as variáveis de ambiente ao Railway

### 2. **Volume Persistente Local (Alternativa)**
Se não quiser usar S3, configure um volume persistente no Railway.

**Configuração:**
```bash
PERSIST_MEDIA_PATH=/var/data/media
```

**No Railway:**
1. Criar um Volume Persistente no projeto
2. Montar em `/var/data/media`
3. Adicionar a variável de ambiente acima

### 3. **Armazenamento Local (Apenas Desenvolvimento)**
Padrão usado em desenvolvimento local. **NÃO usar em produção** pois os arquivos serão perdidos.

## Como Verificar Qual Backend Está Ativo

O Django registra uma mensagem de log ao iniciar indicando qual backend está sendo usado:
- `✅ Usando AWS S3 para armazenamento de mídia`
- `✅ Usando volume persistente em: /var/data/media`
- `⚠️ AVISO: Usando armazenamento local em produção`

Verifique os logs do Railway para confirmar.

## Testar o Armazenamento

1. Upload um certificado ou padrão
2. Anote o ID do histórico
3. Reinicie o container no Railway
4. Verifique se o arquivo ainda está acessível

## Dependências Adicionadas

- `django-storages==1.14.2` - Suporte a múltiplos backends de storage
- `boto3==1.34.0` - SDK AWS para S3

## Próximas Etapas

**Escolher uma opção:**

1. **Para usar S3 (recomendado):**
   - Criar bucket S3
   - Criar usuário IAM
   - Adicionar variáveis de ambiente ao Railway
   - Fazer deploy

2. **Para usar Volume Persistente:**
   - Criar volume no Railway
   - Adicionar variável de ambiente
   - Fazer deploy

**Após configurar:**
- Fazer novo upload de arquivos (os antigos locais serão perdidos)
- Testar com reinício do container

## Referências

- [Django Storages Docs](https://django-storages.readthedocs.io/)
- [AWS S3 Setup for Django](https://django-storages.readthedocs.io/en/latest/backends/amazon_S3.html)
- [Railway Documentation](https://docs.railway.app/)
