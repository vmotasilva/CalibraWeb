# Guia Completo: Configurar AWS S3 para CalibraWeb

## Passo 1: Criar um Bucket S3 na AWS

1. **Acesse** https://console.aws.amazon.com/s3/
2. **Clique** em "Create bucket"
3. **Preencha:**
   - Bucket name: `calibraweb-media` (ou algo único)
   - Region: `us-east-1` (ou sua região preferida)
4. **Desça** até "Block Public Access settings"
   - ✓ Desmarque "Block all public access"
   - ✓ Desmarque "Block public access to buckets and objects granted through new access control lists (ACLs)"
   - ✓ Desmarque "Block public access to buckets and objects granted through any access control lists (ACLs)"
   - Mantenha "Block public access to buckets and objects granted through new public bucket policies" marcado
5. **Clique** em "Create bucket"

## Passo 2: Configurar Política de Acesso Público do Bucket

1. **No painel do S3**, clique no seu bucket `calibraweb-media`
2. **Clique em "Permissions"**
3. **Desça até "Bucket policy"** e clique "Edit"
4. **Cole esta política** (substitua `calibraweb-media` pelo nome do seu bucket):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::calibraweb-media/*"
        }
    ]
}
```

5. **Clique "Save changes"**

## Passo 3: Criar um Usuário IAM

1. **Acesse** https://console.aws.amazon.com/iam/
2. **Clique em "Users"** (no menu esquerdo)
3. **Clique "Create user"**
4. **Preencha:**
   - Username: `calibraweb-app`
5. **Clique "Next"**
6. **Em "Permissions options"**, escolha "Attach policies directly"
7. **Procure e selecione** `AmazonS3FullAccess`
8. **Clique "Create user"**

## Passo 4: Criar Chaves de Acesso

1. **Clique no usuário** `calibraweb-app` que acabou de criar
2. **Clique na aba "Security credentials"**
3. **Desça até "Access keys"** e clique "Create access key"
4. **Escolha:** "Other" (para aplicação)
5. **Clique "Create access key"**
6. **Você verá:**
   - Access Key ID
   - Secret Access Key
   
⚠️ **IMPORTANTE:** Copie e guarde estas chaves em um local seguro! Você não conseguirá ver a Secret Access Key novamente.

## Passo 5: Configurar Variáveis de Ambiente no Railway

1. **Acesse** https://railway.app/project/seu-projeto-id
2. **Clique no seu projeto CalibraWeb**
3. **Clique em "Variables"** (no menu esquerdo)
4. **Clique "New Variable"** e adicione:

```
USE_S3=True
AWS_ACCESS_KEY_ID=sua_access_key_id_aqui
AWS_SECRET_ACCESS_KEY=sua_secret_access_key_aqui
AWS_STORAGE_BUCKET_NAME=calibraweb-media
AWS_S3_REGION_NAME=us-east-1
```

**Exemplo completo:**
```
USE_S3=True
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_STORAGE_BUCKET_NAME=calibraweb-media
AWS_S3_REGION_NAME=us-east-1
```

5. **Clique "Save"** em cada variável

## Passo 6: Fazer o Deploy

1. **Volte para o terminal local (seu computador)**
2. **Execute:**
   ```bash
   cd c:\CalibraWeb
   git pull origin main
   ```

3. **Faça um pequeno commit para disparar o deploy:**
   ```bash
   git log --oneline -1
   ```
   (Copie o hash do último commit)

4. **Se precisar, faça um commit vazio:**
   ```bash
   git commit --allow-empty -m "Deploy: Ativar S3 para armazenamento persistente"
   git push origin main
   ```

5. **Railway fará o deploy automaticamente**

## Passo 7: Verificar se Está Funcionando

1. **Acesse** https://calibraweb.up.railway.app/metrologia/historico/610/editar/
2. **Faça upload de um certificado novo**
3. **Verifique nos logs do Railway** que você vê:
   ```
   ✅ Usando AWS S3 para armazenamento de mídia
   ```

4. **Acesse** https://console.aws.amazon.com/s3/ e navegue até seu bucket
5. **Você deve ver uma pasta `media/`** com os arquivos

## Passo 8: Testar Persistência

1. **Vá ao painel do Railway**
2. **Clique em "Redeploy"** para reiniciar o container
3. **Após reiniciar**, os arquivos devem continuar acessíveis
4. **Acesse o certificado** - deve carregar normalmente!

## Troubleshooting

### Erro: "Arquivo não encontrado"
- Verifique que `USE_S3=True` está definido
- Verifique as credenciais AWS
- Verifique o nome do bucket

### Erro: "Access Denied"
- Verifique se o usuário IAM tem `AmazonS3FullAccess`
- Verifique se a política do bucket está correta

### Erro: "Invalid credentials"
- Verifique se copiou corretamente Access Key ID e Secret
- Verifique se não há espaços extras

## Próximos Passos

Após confirmar que está funcionando:
1. ✅ Todos os certificados novos serão armazenados em S3
2. ✅ Arquivos persistem mesmo com reinício do container
3. ✅ Escalabilidade garantida para crescimento

**Se tiver dúvidas em algum passo, me avise!**
