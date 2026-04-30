# 🚀 COMO RESOLVER: PDFs Desaparecendo no Railway

## 🎯 AÇÃO NECESSÁRIA NO RAILWAY DASHBOARD

Siga estes passos **EXATAMENTE** para configurar o volume persistente:

---

## PASSO 1: Acessar o Projeto no Railway

1. Acesse [railway.app](https://railway.app)
2. Faça login com sua conta
3. Clique no seu projeto `CalibraWeb`
4. Você deve estar na aba **Canvas**

---

## PASSO 2: Configurar o Volume Persistente

### 2.1 Abrir o Menu de Volumes

1. Clique no serviço **web** (o ícone que representa Django/Gunicorn)
2. No painel direito, procure por **Environment**
3. Desça até encontrar a seção **Volumes**

### 2.2 Criar um Novo Volume

1. Clique no botão **+ Create Volume**
2. Configure com estes valores:

```
Mount Path: /data/media
Size: 10GB
```

3. Clique em **Create**

> ⚠️ Se não tiver a opção de criar volume, você pode estar no plano Free. 
> Volumes persistentes estão disponíveis em planos pagos do Railway.

---

## PASSO 3: Adicionar Variável de Ambiente

1. Ainda no painel do serviço **web**
2. Vá para a aba **Variables**
3. Clique em **+ Create Variable**
4. Preencha:

```
Name: PERSIST_MEDIA_PATH
Value: /data/media
```

5. Clique em **Create** ou **Save**

---

## PASSO 4: Fazer Deploy das Mudanças

1. Volte ao seu computador
2. O código já foi atualizado localmente
3. Verifique que os arquivos foram modificados:

```bash
cd c:\CalibraWeb
git status
```

Você deve ver:
```
Modified:   config/settings.py
Modified:   railway.toml
Untracked:  setup_persistent_storage.py
Untracked:  SOLUCAO_PDFS_PERDIDOS.md
```

4. Fazer commit e push:

```bash
git add config/settings.py railway.toml setup_persistent_storage.py
git commit -m "Configure persistent storage for media files on Railway"
git push origin main
```

5. **Aguarde o deploy automático** no Railway
   - O Railway detectará o push automaticamente
   - Você verá um novo deployment iniciando
   - Pode levar 2-5 minutos

---

## PASSO 5: Verificar se Está Funcionando

### 5.1 Verificar o Build

1. No Railroad Dashboard, vá para **Deployments**
2. Você deve ver um novo deployment com:
   - Mensagem do commit: "Configure persistent storage for media files on Railway"
   - Status: **Building** → **Deployed** ✅

### 5.2 Testar Upload de PDF

1. Acesse a aplicação:
   ```
   https://calibraweb.up.railway.app
   ```

2. Faça login

3. Navegue até um histórico de calibração
   - Metrologia → Instrumentos → Selecione um instrumento
   - Clique em um histórico de calibração

4. **Anexe um certificado PDF**:
   - Clique no botão para anexar certificado
   - Selecione um arquivo PDF
   - Clique em "Anexar"

5. Verifique que:
   - ✅ O PDF foi salvo
   - ✅ Você consegue fazer download
   - ✅ Você consegue visualizar

### 5.3 Testar Persistência

1. No Railroad Dashboard
2. Acesse o seu serviço web
3. Clique em **Restart** (no topo)
4. Aguarde 30-60 segundos para o restart completar

5. Volte à aplicação:
   - Recarregue a página
   - **O PDF deve estar lá!** (não foi perdido)

---

## ✅ PRONTO!

Se o PDF continuou acessível após o restart, a configuração funcionou! 🎉

Os PDFs agora serão salvos em `/data/media` que é um volume persistente no Railway e **NÃO será perdido** quando o container reiniciar.

---

## 🆘 SE ALGO DER ERRADO

### Erro: "Mount path '/data/media' not found"

**Solução**: O volume ainda não foi criado ou está no serviço errado.
- Verifique que criou o volume no serviço **web** (Django)
- Não é no serviço do banco de dados

### Erro: "Variable PERSIST_MEDIA_PATH not found"

**Solução**: A variável de ambiente não foi adicionada.
- Verifique no painel do serviço web → Variables
- Certifique-se que está em **web**, não em outro serviço

### PDFs ainda desaparecem após restart

**Solução**: Pode ser que o volume não esteja mountado corretamente.
1. Reinicie o serviço completamente (não apenas restart)
2. Verifique os logs:
   - Services → web → Logs
   - Procure por: "✅ Usando volume persistente em: /data/media"

3. Se não encontrar essa mensagem, execute no shell do Railway:
   ```bash
   ls -la /data/media/
   ```
   
   Deve retornar o conteúdo do diretório (mesmo que vazio)

### O volume está cheio

**Solução**: Aumentar o tamanho
1. Railway Dashboard → Services → web
2. Volumes → Selecione o volume
3. Clique em **Edit** 
4. Aumente o **Size** para 20GB ou mais

---

## 📞 SUPORTE

Se ainda tiver problemas:

1. Verifique os **Logs** do Railway
2. Procure por erros relacionados a `MEDIA_ROOT` ou `/data/media`
3. Certifique-se que todas as 3 etapas foram feitas:
   - ✅ Volume criado
   - ✅ Variável PERSIST_MEDIA_PATH adicionada
   - ✅ Deploy feito com os novos arquivos

