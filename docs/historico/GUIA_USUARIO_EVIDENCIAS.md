# 📖 GUIA DO USUÁRIO - Sistema de Evidência de Listas Assinadas

## Para Instrutores e Administradores de Treinamento

---

## 📋 Índice

1. [O que é esse sistema?](#o-que-é-esse-sistema)
2. [Pré-requisitos](#pré-requisitos)
3. [Passo a Passo Completo](#passo-a-passo-completo)
4. [Problemas e Soluções](#problemas-e-soluções)
5. [Dicas e Boas Práticas](#dicas-e-boas-práticas)

---

## O que é esse sistema?

Este é um **sistema de archivamento digital de evidências** de treinamentos.

Funciona assim:

```
Você imprime uma lista de presença (PDF) do sistema
         ↓
Entrega para os participantes assinarem
         ↓
Recolhe a lista assinada
         ↓
Faz um scan (ou foto) da lista
         ↓
Faz upload da imagem/PDF no sistema ← VOCÊ ESTÁ AQUI
         ↓
Sistema armazena como prova de que o treinamento aconteceu
```

**Por que?** Para conformidade com regulações (ISO, auditoria, LGPD). A lista assinada é a **evidência oficial** de que o treinamento foi realizado.

---

## Pré-requisitos

- ✓ Você está logado no sistema CALIBRA WEB
- ✓ Você criou uma planejamento/lista de presença
- ✓ Você gerou e imprimiu a lista de presença
- ✓ Participantes assinaram a lista (papel)
- ✓ Você fez um scan ou fotografia da lista assinada

**Formatos aceitos:**
- PDF (recomendado para scans)
- JPG/JPEG (foto com câmera/smartphone)
- PNG (imagem sem compressão)
- TIFF (scan profissional)

**Tamanho máximo:** 50 MB

---

## Passo a Passo Completo

### 1️⃣ Acesse a Lista de Presença

```
Navegue para: http://localhost:8000/procedures/listas-presenca/
```

Você verá uma tabela com todas as listas criadas:

```
┌──────┬───────────────┬──────────────────┬──────────┬────────────┐
│ #    │ CÓDIGO        │ TÍTULO           │ INSTRUTOR│ ASSINADA   │
├──────┼───────────────┼──────────────────┼──────────┼────────────┤
│ 1    │ LP2025-0068   │ Treinamento XYZ  │ João     │ ✓ SIM      │
│ 2    │ LP2025-0069   │ Treinamento ABC  │ Maria    │ ✗ NÃO      │
│ 3    │ LP2025-0070   │ Treinamento DEF  │ Pedro    │ ✓ SIM      │
└──────┴───────────────┴──────────────────┴──────────┴────────────┘
```

**Símbolos:**
- ✓ = Evidência já foi carregada
- ✗ = Sem evidência carregada ainda

---

### 2️⃣ Selecione uma Lista

Clique no **código da lista** (ex: LP2025-0069) para abrir seus detalhes.

Você verá:
- Informações da lista (data, instrutor, etc.)
- Lista de participantes
- Botões de ação (Gerar PDF, etc.)
- **NOVO: Botão "Upload Assinada"** ← Clique aqui!

```
┌────────────────────────────────────────┐
│ DETALHES DA LISTA DE PRESENÇA         │
│                                        │
│ Código: LP2025-0069                   │
│ Título: Treinamento ABC               │
│ Data: 02/01/2026                      │
│ Instrutor: Maria Silva                │
│                                        │
│ [Gerar PDF] [Imprimir] [Upload ✓]     │
│                    ↑ Clique aqui!      │
└────────────────────────────────────────┘
```

---

### 3️⃣ Clique em "Upload Assinada"

Você será levado à página de upload:

```
┌──────────────────────────────────────────────┐
│ UPLOAD DE LISTA DE PRESENÇA ASSINADA        │
│                                              │
│ 📋 INFORMAÇÕES DA LISTA                     │
│    Código: LP2025-0069                      │
│    Título: Treinamento ABC                  │
│    Instrutor: Maria Silva                   │
│                                              │
│ ⚠️  POR QUE ISSO IMPORTA?                    │
│    A lista assinada é prova de que o       │
│    treinamento foi realizado. Importante   │
│    para conformidade e auditoria.          │
│                                              │
│ ✅ SITUAÇÃO ATUAL: Nenhum arquivo ainda     │
│                                              │
│ 📁 SELECIONAR ARQUIVO                       │
│    ┌──────────────────────────────────────┐ │
│    │ Arraste arquivo aqui ou clique      │ │
│    │ para selecionar                     │ │
│    └──────────────────────────────────────┘ │
│                                              │
│ [ENVIAR EVIDÊNCIA]                         │
│                                              │
│ 💡 DICAS DE QUALIDADE                       │
│    • Resolução: 300 DPI mínimo             │
│    • Iluminação: Bem iluminado             │
│    • Assinaturas: Claramente visíveis      │
│                                              │
└──────────────────────────────────────────────┘
```

---

### 4️⃣ Selecione o Arquivo

Você pode:

**Opção A: Drag-and-drop**
1. Tenha seu PDF ou imagem em alguma pasta
2. Arraste o arquivo para a área cinzenta
3. Sistema detectará automaticamente

**Opção B: Clique para selecionar**
1. Clique na área cinzenta
2. Janela de seleção abrirá
3. Navegue até seu arquivo
4. Clique em "Abrir"

**Formatos aceitos:**
- ✓ PDF (melhor para scans)
- ✓ JPG/JPEG (foto smartphone)
- ✓ PNG (imagem lossless)
- ✓ TIFF (scan profissional)

**Formatos rejeitados:**
- ✗ Word (.doc, .docx)
- ✗ Excel (.xls, .xlsx)
- ✗ Texto (.txt)
- ✗ Executável (.exe)
- ✗ ZIP (.zip, .rar)

---

### 5️⃣ Verifique o Preview

Após selecionar o arquivo, você verá:

```
┌──────────────────────────────────────┐
│ ARQUIVO SELECIONADO                 │
│                                      │
│ 📄 lista_assinada_20260102.pdf      │
│ Tamanho: 2.4 MB                     │
│ Status: ✓ Pronto para envio         │
└──────────────────────────────────────┘
```

**Se houver erro:**
```
┌──────────────────────────────────────┐
│ ❌ ERRO NA VALIDAÇÃO                │
│                                      │
│ O arquivo "documento.doc" não é     │
│ permitido. Formatos aceitos:        │
│ • PDF, JPG, JPEG, PNG, TIFF        │
│                                      │
│ Ação: Converta para PDF e tente     │
│ novamente                            │
└──────────────────────────────────────┘
```

---

### 6️⃣ Envie o Arquivo

Clique em **"ENVIAR EVIDÊNCIA"**

Sistema fará:
1. ✓ Validar novamente o arquivo
2. ✓ Armazenar em local seguro
3. ✓ Registrar data/hora do upload
4. ✓ Atualizar status na lista
5. ✓ Voltar à página anterior

```
✅ SUCESSO!

Sua evidência foi armazenada com sucesso.
Arquivo: lista_assinada_20260102.pdf
Carregado em: 02/01/2026 14:30:00

A lista de presença agora tem evidência arquivada.
```

---

### 7️⃣ Confirme na Lista de Presença

Após upload, você voltará à página de detalhe:

```
┌────────────────────────────────────────────┐
│ DETALHES DA LISTA DE PRESENÇA             │
│                                            │
│ 📋 EVIDÊNCIA DOCUMENTAL                   │
│                                            │
│ ✓ Arquivo Armazenado                      │
│                                            │
│ Nome: lista_assinada_20260102.pdf         │
│ Upload em: 02/01/2026 14:30:00            │
│ Tamanho: 2.4 MB                           │
│                                            │
│ [VISUALIZAR] [REMOVER]                    │
│                                            │
└────────────────────────────────────────────┘
```

---

### 8️⃣ Visualize o Arquivo (Opcional)

Clique em **"VISUALIZAR"** para:
- Ver o PDF/imagem no navegador
- Verificar se a qualidade está boa
- Validar assinaturas

Não será feito download automático - abre no navegador mesmo.

---

### 9️⃣ Verifique na Lista Geral

Volte para `/listas-presenca/`:

```
┌───────┬────────────────┬──────────┬────────┬──────────┐
│ #     │ CÓDIGO         │ TÍTULO   │ INST.  │ ASSINADA │
├───────┼────────────────┼──────────┼────────┼──────────┤
│ 2     │ LP2025-0069    │ ABC      │ Maria  │ ✓ SIM    │  ← Agora mostra ✓
└───────┴────────────────┴──────────┴────────┴──────────┘
```

Badge mudou de **✗ NÃO** para **✓ SIM** 🎉

---

## Problemas e Soluções

### ❌ "Arquivo não é permitido"

**Possíveis causas:**
1. Extensão incorreta
2. Arquivo corrompido
3. Formato não suportado

**Solução:**
1. Verifique a extensão (.pdf, .jpg, .png, .tiff)
2. Se for imagem, tente converter para JPG
3. Se for PDF, tente abrir em leitor PDF e salvar novamente
4. Tente upload novamente

### ❌ "Arquivo é muito grande"

**Possível causa:** Arquivo > 50 MB

**Solução:**
1. Se é scan: Reduza a resolução (200 DPI em vez de 300)
2. Se é foto: Comprima a imagem (use app ou Windows)
3. Se é PDF: Comprima o PDF (use ferramenta online)
4. Tente novamente

### ❌ "Erro ao fazer upload"

**Possíveis causas:**
1. Conexão de internet perdida
2. Servidor indisponível
3. Permissão insuficiente

**Solução:**
1. Verifique sua conexão de internet
2. Recarregue a página (F5)
3. Tente novamente em alguns minutos
4. Se persistir, contate administrador

### ❌ "Não consigo acessar a página de upload"

**Possível causa:** Não está logado ou sem permissão

**Solução:**
1. Verifique se está logado (veja canto superior)
2. Se não está, faça login
3. Se está, contate administrador para permissões

### ✅ "Quero remover e refazer o upload"

**Processo:**
1. Clique em **"REMOVER"** na seção de evidência
2. Confirme a remoção
3. Sistema remove o arquivo
4. Clique novamente em **"Upload Assinada"**
5. Selecione novo arquivo
6. Envie

---

## Dicas e Boas Práticas

### 🎯 Para Melhor Qualidade

**Scanning:**
- Use resolução 300 DPI (profissional)
- Papel bem iluminado
- Certifique-se que todas as assinaturas estão visíveis
- Verifique que nomes estão legíveis

**Fotografia (com smartphone):**
- Use boa iluminação (luz natural ideal)
- Mantenha câmera reta (não inclinada)
- Evite reflexos/brilhos nas assinaturas
- Tire múltiplas fotos, escolha a melhor

**Conversão para PDF:**
```
Word → PDF: Arquivo > Salvar Como > Formato: PDF
Imagem → PDF: Use site online (ex: smallpdf.com)
Múltiplas imagens → PDF: Use app/software específico
```

### ⏰ Timing

- ✓ Faça upload **imediatamente** após coletar as assinaturas
- ✓ Não espere dias (você pode esquecer)
- ✓ Se houver múltiplas turmas, faça upload no mesmo dia
- ✓ Registre data/hora do arquivo para rastreamento

### 🔄 Se Errar

1. Assinatura ilegível? → Remova e faça novo scan
2. Arquivo corrompido? → Tente converter novamente
3. Imagem de cabeça para baixo? → Rotacione antes de upload

**Processo de correção:**
```
[REMOVER] → [Aguarde confirmação] → [OK] 
→ [Upload Assinada] → [Novo arquivo] 
→ [ENVIAR EVIDÊNCIA]
```

### 📊 Mantendo Registro

**Para sua organização pessoal:**
- Mantenha cópia do PDF original (backup)
- Anote a data do upload
- Se houver correções, atualize suas notas

**Sistema faz automaticamente:**
- ✓ Registra data/hora do upload
- ✓ Armazena arquivo seguro
- ✓ Mantém disponível para auditoria
- ✓ Rastreia histórico

### ✅ Checklist Antes de Fazer Upload

- [ ] Arquivo é um dos formatos aceitos? (PDF, JPG, PNG, TIFF)
- [ ] Arquivo é menor que 50 MB?
- [ ] Assinaturas estão claramente visíveis?
- [ ] Todos os nomes dos participantes estão legíveis?
- [ ] Está logado no sistema?
- [ ] Selecionou a lista correta?

---

## FAQ Rápido

**P: Quanto tempo leva o upload?**
R: Geralmente 5-30 segundos dependendo da internet e tamanho do arquivo.

**P: Posso fazer upload de múltiplas evidências?**
R: Não, apenas uma evidência por lista. Se precisar substituir, remova a anterior primeiro.

**P: O arquivo original (papel) precisa ser guardado?**
R: Depende da política da empresa. Sistema faz cópia digital segura, mas alguns clientes preferem manter original.

**P: Quem pode fazer upload?**
R: Qualquer usuário logado (idealmente instrutor ou admin do treinamento).

**P: Como é o backup?**
R: Arquivos são armazenados em `/media/listas_presenca_assinadas/`. Fazer backup regular deste diretório.

**P: Posso acessar de qualquer lugar?**
R: Sim, qualquer computador/dispositivo com acesso ao sistema pode fazer upload ou visualizar.

**P: Quanto tempo os arquivos são guardados?**
R: Indefinitamente (ou conforme política de retenção da empresa). Recomendado guardar no mínimo 2 anos.

---

## Contato e Suporte

Se encontrar problemas:

1. **Consulte este guia** - Tente encontrar a solução aqui
2. **Verifique sua conexão** - Às vezes é simples
3. **Contate administrador** - Para questões de permissão ou erros do servidor
4. **Reportar bug** - Se achar um erro consistente

**Informações úteis para relatar:**
- O que você estava tentando fazer
- Qual erro recebeu (copie a mensagem)
- Seu navegador e versão
- Se o problema é consistente ou ocasional

---

## 🎉 Pronto!

Você agora sabe como fazer upload de listas de presença assinadas como evidência documental.

**Processo resumido:**
1. Acesse a lista na tabela
2. Clique "Upload Assinada"
3. Selecione o arquivo (PDF/imagem)
4. Clique "Enviar Evidência"
5. Pronto! Evidência armazenada

Qualquer dúvida, consulte este guia ou contate seu administrador de sistema.

---

**Desenvolvido em:** 02/01/2026
**Última atualização:** 02/01/2026
**Versão:** 1.0
