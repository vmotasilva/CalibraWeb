# 🧪 GUIA DE TESTE PRÁTICO - Upload de Padrões

## 🎯 Objetivo

Validar que a funcionalidade de upload de padrões está funcionando corretamente em produção.

---

## ✅ Pré-requisitos

- [ ] Acesso à URL: https://calibraweb.up.railway.app
- [ ] Usuário logado com permissão no módulo de metrologia
- [ ] Um histórico de calibração já criado (ou criar um novo)
- [ ] Arquivos PDF para teste (mínimo 2-3)
- [ ] Browser moderno (Chrome, Firefox, Safari, Edge)

---

## 🔍 Teste 1: Acesso à Página

### Passos:
1. Acesse: `https://calibraweb.up.railway.app/metrologia/`
2. Procure por um instrumento e seu histórico
3. Clique em **"Editar Histórico"** (ou a URL: `/metrologia/historico/{id}/editar/`)
4. A página deve carregar sem erros

### ✓ Critérios de Sucesso:
- [ ] Página carrega normalmente
- [ ] Seção "Padrões de Calibração" é visível
- [ ] Não há erros no console (F12 → Console)

---

## 🎨 Teste 2: UI da Upload Box

### Passos:
1. Localize a seção "Padrões de Calibração"
2. Se estiver recolhida, expanda clicando no header
3. Observe a upload box

### ✓ Critérios de Sucesso:
- [ ] Box tem bordas em cor azul (info)
- [ ] Texto diz "Clique ou arraste arquivos aqui"
- [ ] Hint inferior diz "Máximo 50MB por arquivo, apenas PDF"
- [ ] Box tem efeito hover (muda de cor ao passar mouse)

---

## 📤 Teste 3: Upload Simples

### Passos:
1. Clique na upload box
2. Selecione **1 arquivo PDF** (< 10MB)
3. Observe a preview de arquivos

### ✓ Critérios de Sucesso:
- [ ] Caixa de seleção de arquivo abre
- [ ] Arquivo aparece na prévia com:
  - [x] Nome do arquivo
  - [x] Tamanho em KB/MB
  - [x] Badge verde "[OK]"
- [ ] Dois botões aparecem: "Enviar Arquivos" e "Cancelar"

### Passos Continuação:
4. Clique no botão "Enviar Arquivos"
5. Aguarde o spinner desaparecer

### ✓ Critérios de Sucesso:
- [ ] Spinner animado aparece durante 2-5 segundos
- [ ] Mensagem verde com "✓ X arquivo(s) enviado(s) com sucesso."
- [ ] PDF aparece na seção "Padrões Anexados" abaixo
- [ ] Contador de padrões atualiza (ex: (1))
- [ ] Upload box volta ao estado vazio

---

## 📤 Teste 4: Upload Múltiplo

### Passos:
1. Clique na upload box novamente
2. Selecione **3 arquivos PDF diferentes**
3. Todos devem aparecer na prévia

### ✓ Critérios de Sucesso:
- [ ] Todos os 3 arquivos aparecem listados
- [ ] Cada um tem o tamanho correto
- [ ] Todos têm badge "[OK]"

### Passos Continuação:
4. Clique "Enviar Arquivos"
5. Aguarde conclusão

### ✓ Critérios de Sucesso:
- [ ] Mensagem mostra "3 arquivo(s) enviado(s)"
- [ ] Todos os 3 PDFs aparecem na lista
- [ ] Contador atualiza para (4) [se havia 1 antes]
- [ ] Não há erros

---

## ❌ Teste 5: Validação - Arquivo Não-PDF

### Passos:
1. Clique na upload box
2. Tente selecionar um arquivo **.txt** ou **.docx**
3. Observe o preview

### ✓ Critérios de Sucesso:
- [ ] Arquivo aparece com ❌ (erro)
- [ ] Mensagem mostra: "Deve ser PDF"
- [ ] Botão "Enviar Arquivos" está **desabilitado**

### Passos Continuação:
4. Adicione um PDF válido
5. Agora o PDF deve estar OK e botão habilitado

---

## ⚠️ Teste 6: Validação - Arquivo Muito Grande

### Passos:
1. Clique na upload box
2. Selecione um arquivo PDF > 50MB (ou 10MB para teste rápido)

### ✓ Critérios de Sucesso:
- [ ] Arquivo aparece com ❌
- [ ] Mensagem mostra: "Arquivo > 50MB"
- [ ] Botão "Enviar" desabilitado

---

## 🎯 Teste 7: Drag and Drop

### Passos:
1. Procure um PDF no seu computador
2. Arraste direto para a upload box
3. Solte o arquivo

### ✓ Critérios de Sucesso:
- [ ] Durante o arraste, a box muda de cor (azul escuro)
- [ ] Ao soltar, o arquivo aparece na prévia
- [ ] Funciona igual ao clique

---

## 🗑️ Teste 8: Remover Padrão

### Passos:
1. Localize um padrão na lista "Padrões Anexados"
2. Clique no ícone 🗑️ (lixo) à direita
3. Uma dialog de confirmação aparece: "Remover este padrão?"

### ✓ Critérios de Sucesso:
- [ ] Dialog de confirmação funciona
- [ ] Clique "OK"

### Passos Continuação:
4. Aguarde a remoção

### ✓ Critérios de Sucesso:
- [ ] Padrão desaparece da lista
- [ ] Nenhum refresh de página
- [ ] Contador decrementa
- [ ] Mensagem "✓ Padrão removido com sucesso"
- [ ] Se era o último: mostra "Nenhum padrão anexado ainda"

---

## 📥 Teste 9: Download de Padrão

### Passos:
1. Clique no botão 📥 (download) de um padrão
2. Arquivo deve ser baixado

### ✓ Critérios de Sucesso:
- [ ] Download inicia automaticamente
- [ ] Arquivo PDF é salvo na pasta Downloads
- [ ] Arquivo tem nome correto

---

## 🔄 Teste 10: Recarregar Página

### Passos:
1. Após fazer upload de padrões
2. Recarregue a página (F5 ou Ctrl+R)
3. Abra a seção "Padrões de Calibração" novamente

### ✓ Critérios de Sucesso:
- [ ] Padrões continuam na lista (persistem no BD)
- [ ] Contador mantém o valor correto
- [ ] Nenhuma perda de dados

---

## 🔐 Teste 11: Segurança - Sem Login

### Passos:
1. Faça logout
2. Tente acessar a URL diretamente: `/metrologia/historico/{id}/editar/`

### ✓ Critérios de Sucesso:
- [ ] Sistema redireciona para login
- [ ] Não pode acessar sem autenticação

---

## 🔐 Teste 12: Segurança - Arquivo Malicioso

### Passos:
1. Crie um arquivo chamado `malware.pdf` (pode ser um .txt renomeado)
2. Tente fazer upload

### ✓ Critérios de Sucesso:
- [ ] Sistema rejeita o arquivo
- [ ] Mostra mensagem de erro
- [ ] Arquivo NÃO é salvo no servidor

---

## 📊 Teste 13: Performance

### Passos:
1. Abra DevTools (F12)
2. Vá à aba "Network"
3. Faça upload de um arquivo 5MB
4. Observe o tempo de requisição

### ✓ Critérios de Sucesso:
- [ ] Requisição completa em < 5 segundos
- [ ] Sem timeouts
- [ ] Resposta é JSON válido

---

## 📱 Teste 14: Responsividade Mobile

### Passos:
1. Abra a página em um celular
2. Expanda seção de padrões
3. Tente fazer upload

### ✓ Critérios de Sucesso:
- [ ] Upload box é responsivo
- [ ] Toque para selecionar funciona
- [ ] Arquivo aparece na prévia
- [ ] Upload completa
- [ ] Não há quebra de layout

---

## 🔍 Teste 15: Console (Erros JavaScript)

### Passos:
1. Abra DevTools (F12 → Console)
2. Faça um upload completo
3. Procure por mensagens vermelhas

### ✓ Critérios de Sucesso:
- [ ] Console está limpo (sem erros vermelhos)
- [ ] Podem haver warnings (amarelo) mas não críticos
- [ ] Logs úteis aparecem (azul/branco)

---

## 📋 Tabela de Resultados

Preencha após cada teste:

| # | Teste | Resultado | Observações |
|---|-------|-----------|-------------|
| 1 | Acesso à página | ✓ | Sem erros |
| 2 | UI upload box | ✓ | Cores OK |
| 3 | Upload simples | ✓ | 1 PDF OK |
| 4 | Upload múltiplo | ✓ | 3 PDFs OK |
| 5 | Validação não-PDF | ✓ | Rejeitado |
| 6 | Validação grande | ✓ | Rejeitado |
| 7 | Drag and drop | ✓ | Funciona |
| 8 | Remover padrão | ✓ | Desaparece |
| 9 | Download padrão | ✓ | Arquivo OK |
| 10 | Recarregar página | ✓ | Dados persistem |
| 11 | Sem login | ✓ | Redireciona |
| 12 | Arquivo malicioso | ✓ | Rejeitado |
| 13 | Performance | ✓ | < 5s |
| 14 | Mobile | ✓ | Responsivo |
| 15 | Console | ✓ | Limpo |

---

## 📝 Relatório de Teste

Caso encontre problemas:

**Problema Encontrado:**
```
Data/Hora: ___/___/_____ __:__
Descrição: _________________________________
Screenshot: [anexar]
Passos para reproduzir: _________________________________
Resultado esperado: _________________________________
Resultado atual: _________________________________
```

**Informações do Ambiente:**
```
Browser: Chrome / Firefox / Safari / Edge
Versão: ___________
Sistema: Windows / macOS / Linux
Resolução: __________
URL: https://calibraweb.up.railway.app/metrologia/historico/{id}/editar/
Usuário: ___________
```

---

## 🎯 Checklist Final

- [ ] Todos os 15 testes passaram ✓
- [ ] Sem erros no console
- [ ] Performance OK
- [ ] Mobile funciona
- [ ] Segurança validada
- [ ] Dados persistem
- [ ] Documentação lida

---

## ✅ Status Final

### Se todos os testes passaram:
🟢 **SOLUÇÃO VALIDADA E APROVADA PARA USO**

### Se encontrou problemas:
🔴 **Entre em contato com o desenvolvedor**

---

## 📞 Dúvidas?

Caso tenha dúvidas durante os testes, consulte:
- `PADROES_UPLOAD_FIX_COMPLETO.md` - Documentação completa
- `DIAGRAMA_UPLOAD_PADROES.md` - Diagramas técnicos
- `RESUMO_FIX_PADROES_UPLOAD.md` - Resumo executivo
- `CHECKLIST_TECNICO_PADROES.md` - Checklist técnico

---

**Data de Teste:** ___/___/_____
**Testador:** _____________________
**Resultado:** ✓ Aprovado / ✗ Falhou
