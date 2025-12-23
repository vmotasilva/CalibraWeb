# ☁️ CONFIGURAR AWS S3 NO RAILWAY (Grátis por 12 meses!)

## 🎯 RESUMO

- **Grátis**: 12 meses de AWS S3 grátis
- **Ilimitado**: 5GB grátis permanentemente
- **Seguro**: Seus PDFs nunca mais vão sumir!
- **Rápido**: Arquivos são servidos da nuvem

---

## 📋 PASSO 1: Criar Conta AWS (5 minutos)

### 1.1 Abrir AWS
```
Acesse: https://aws.amazon.com
```

### 1.2 Criar Conta
```
1. Clique em "Create AWS Account" (canto superior direito)
2. Preencha:
   ✓ Email: seu-email@gmail.com
   ✓ Senha: (crie uma senha forte)
   ✓ Nome da Conta: calibraweb-s3
3. Clique em "Create Account"
```

### 1.3 Confirmar Email
```
1. Verifique seu email
2. Clique no link de confirmação
3. Complete o cadastro com dados do cartão (não vai cobrar no free tier)
```

---

## 🪣 PASSO 2: Criar um S3 Bucket (5 minutos)

### 2.1 Acessar S3
```
1. Log in na AWS com seu email
2. No topo, procure por "Services" ou "Search"
3. Procure por "S3" (Simple Storage Service)
4. Clique em "S3"
```

### 2.2 Criar Bucket
```
1. Clique em "Create Bucket"
2. Preencha:
   ✓ Bucket name: calibraweb-media
     (IMPORTANTE: Números, letras e traços OK. Espaços NÃO!)
   ✓ Region: us-east-1 (padrão OK)
3. Desça até encontrar "Block all public access"
   ✗ DESMARQUE "Block all public access"
   (Sim, desmarque para que os PDFs sejam acessíveis)
4. Clique em "Create bucket"
```

**Pronto! Seu bucket foi criado!** ✅

---

## 🔑 PASSO 3: Criar Credenciais AWS (5 minutos)

### 3.1 Ir para IAM
```
1. No AWS Console, procure por "Services" → "IAM"
2. Clique em "IAM" (Identity and Access Management)
```

### 3.2 Criar Usuario
```
1. No menu esquerdo, clique em "Users"
2. Clique em "Create User"
3. Preencha:
   ✓ User name: calibraweb-app
4. Clique em "Next"
```

### 3.3 Adicionar Permissão
```
1. Em "Permissions options", selecione "Attach policies directly"
2. Na caixa "Permissions policies", procure por: AmazonS3FullAccess
3. MARQUE a caixa ao lado de "AmazonS3FullAccess"
4. Clique em "Next"
5. Clique em "Create user"
```

### 3.4 Obter as Credenciais
```
1. Clique no usuário "calibraweb-app" que acabou de criar
2. Vá em "Security credentials"
3. Procure por "Access keys"
4. Clique em "Create access key"
5. Selecione "Application running outside AWS"
6. Clique em "Next"
7. Clique em "Create access key"
8. COPIE e SALVE em um lugar seguro:
   ✓ Access Key ID:     AKIAIOSFODNN7EXAMPLE
   ✓ Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**⚠️ GUARDE ESSAS CREDENCIAIS! Você vai usar em breve.**

---

## 🚀 PASSO 4: Configurar no Railway (3 minutos)

### 4.1 Acessar Railway
```
Acesse: https://railway.app
```

### 4.2 Ir ao Projeto
```
1. Clique em "CalibraWeb"
2. Clique no serviço "web"
3. Vá para a aba "Variables"
```

### 4.3 Adicionar Variáveis
```
Clique em "+ New Variable" e adicione EXATAMENTE:
```

**Variável 1:**
```
Name:  USE_S3
Value: True
```

**Variável 2:**
```
Name:  AWS_ACCESS_KEY_ID
Value: AKIAIOSFODNN7EXAMPLE
```
(Cole o valor que você copiou da AWS)

**Variável 3:**
```
Name:  AWS_SECRET_ACCESS_KEY
Value: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```
(Cole o valor secreto que você copiou)

**Variável 4:**
```
Name:  AWS_STORAGE_BUCKET_NAME
Value: calibraweb-media
```

**Variável 5:**
```
Name:  AWS_S3_REGION_NAME
Value: us-east-1
```

### 4.4 Deploy
```
1. Volte ao seu PC
2. Execute no terminal:
```

```powershell
cd C:\CalibraWeb
git push origin main
```

```
3. No Railway, vá em "Deployments"
4. Aguarde o novo deployment terminar (Building → Deployed ✅)
```

---

## ✅ PASSO 5: Testar (2 minutos)

### 5.1 Login na Aplicação
```
https://calibraweb.up.railway.app
```

### 5.2 Anexar um PDF
```
1. Metrologia → Instrumentos → Selecione um
2. Clique em um histórico de calibração
3. Anexe um certificado PDF
4. Clique em "Anexar"
```

### 5.3 Verificar
```
Se o PDF apareceu = SUCESSO! ✅
Os PDFs agora estão seguros na AWS S3!
```

---

## 🎉 PRONTO!

Seus PDFs agora estão armazenados na **nuvem da Amazon** e **NUNCA mais vão sumir**, mesmo que:

- ✅ O servidor reinicie
- ✅ A aplicação caia
- ✅ Você mude de hosting
- ✅ O banco de dados delete

Os arquivos estão **permanentes na AWS S3**! 🚀

---

## 💰 CUSTOS

- **Primeiros 12 meses**: GRÁTIS!
- **Depois**: ~$0,023 por GB/mês (muito barato!)
- **5GB grátis permanentemente** mesmo depois dos 12 meses

---

## 🆘 PROBLEMAS COMUNS

### "Access Denied" ao enviar arquivo
```
Solução: Verifique se:
1. AWS_ACCESS_KEY_ID está correto
2. AWS_SECRET_ACCESS_KEY está correto
3. O usuario tem permissão AmazonS3FullAccess
```

### "Bucket not found"
```
Solução: Verifique se:
1. AWS_STORAGE_BUCKET_NAME é exatamente: calibraweb-media
2. O bucket foi criado com sucesso na AWS
```

### PDF não aparece após envio
```
Solução:
1. Verifique os logs do Railway (Logs → procure por erros S3)
2. Reinicie o serviço web
3. Tente novamente
```

---

## 📝 CHECKLIST FINAL

- [ ] Criei conta na AWS
- [ ] Criei bucket S3 "calibraweb-media"
- [ ] Criei usuário IAM "calibraweb-app"
- [ ] Copiei Access Key ID e Secret Access Key
- [ ] Adicionei 5 variáveis no Railway
- [ ] Fiz git push origin main
- [ ] Esperei o deploy terminar
- [ ] Anexei um PDF de teste
- [ ] PDF foi salvo com sucesso
- [ ] Tudo funcionando! 🎉

