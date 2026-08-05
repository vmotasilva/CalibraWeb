# 🧪 GUIA DE TESTES PRÁTICOS

## 📋 Teste Manual Completo (30 minutos)

### Pré-requisitos
- Servidor rodando: `python manage.py runserver`
- URL: `http://127.0.0.1:8000/`
- Estar logado no sistema
- Ter dados de teste (solicitações com cotações)

---

## ✅ Teste 1: Visualizar Aba de Cotações

**Objetivo:** Verificar que a aba aparece corretamente

**Passos:**

1. Acesse: `http://127.0.0.1:8000/instrumento/1/detalhes/`
   
2. Procure pelas abas no topo:
   ```
   [📜 Certificados] [📋 Cotações] [🚚 Rastreio] [⚠️ Ocorrências]
   ```

3. Verifique:
   - [ ] Aba "Cotações" existe
   - [ ] Tem um ícone 📋
   - [ ] Tem badge de contagem (se houver cotações)
   - [ ] Clique abre/fecha corretamente

**Resultado Esperado:** ✅ Aba visível com badge de contagem

---

## ✅ Teste 2: Expandir Seções do Accordion

**Objetivo:** Testar accordion responsivo

**Passos:**

1. Na aba "Cotações", você verá 3 seções:
   ```
   ├─ Registros de Calibração
   ├─ Rastreio em Laboratório
   └─ Substituições/Aquisições
   ```

2. Clique em cada uma para expandir/recolher

3. Verifique:
   - [ ] Seção "Registros de Calibração" expande
   - [ ] Mostra cards de cotações
   - [ ] Clique novamente recolhe
   - [ ] "Rastreio" expande/recolhe
   - [ ] "Substituições" expande/recolhe

**Resultado Esperado:** ✅ Accordion funciona smooth

---

## ✅ Teste 3: Visualizar Dados de Calibração

**Objetivo:** Testar exibição de dados na seção de Calibração

**Passos:**

1. Expanda "Registros de Calibração"

2. Procure por um card como:
   ```
   Cotação SOL-2025-0003 - [Tecnolab] - Status
   ├─ Local: No Local
   ├─ Prazo: 2 dias
   ├─ Valor: R$ 250,00
   ├─ Data Prevista: 20/12/2025
   ├─ Data Realizada: [pendente]
   ├─ Técnico: [vazio]
   └─ Botões: [Ver Solicitação] [Atualizar Data]
   ```

3. Verifique:
   - [ ] Informações exibidas corretamente
   - [ ] Badge de status correto
   - [ ] Botões visíveis
   - [ ] Valores formatados (R$, datas)

**Resultado Esperado:** ✅ Card com todas as informações

---

## ✅ Teste 4: Abrir Modal de Calibração

**Objetivo:** Testar abertura do modal

**Passos:**

1. No card de calibração, clique em "Atualizar Data"

2. Um modal deve aparecer:
   ```
   ╔═══════════════════════════════════╗
   ║ Atualizar Data de Calibração      ║
   ╠═══════════════════════════════════╣
   ║ Data Realizada *      [16/12/2025]║
   ║ Técnico Responsável   [João Silva]║
   ║ Observações           [...]       ║
   ╠═══════════════════════════════════╣
   ║          [Cancelar] [Atualizar]   ║
   ╚═══════════════════════════════════╝
   ```

3. Verifique:
   - [ ] Modal abre com animação fade-in
   - [ ] Campos estão preenchidos corretamente
   - [ ] Data está pré-preenchida
   - [ ] Botões visíveis
   - [ ] Pode fechar com X ou Cancelar

**Resultado Esperado:** ✅ Modal exibido corretamente

---

## ✅ Teste 5: Preencher e Submeter Modal

**Objetivo:** Testar validação e submit do formulário

**Passos:**

1. No modal aberto, edite os campos:
   ```
   Data Realizada: 16/12/2025 (deixar como está)
   Técnico: João Silva (deixar como está)
   Observações: Teste realizado com sucesso
   ```

2. Clique "Atualizar"

3. Verifique:
   - [ ] Modal desaparece
   - [ ] Página redireciona
   - [ ] Mensagem "sucesso" aparece (se configurada)
   - [ ] Volta para instrumento
   - [ ] Card mostra dados atualizados

**Resultado Esperado:** ✅ Dados atualizados, redireciona

---

## ✅ Teste 6: Visualizar Timeline de Rastreio

**Objetivo:** Testar exibição da timeline

**Passos:**

1. Expanda "Rastreio em Laboratório"

2. Procure por um card com timeline:
   ```
   ●────────●────────●
   ✅        ℹ️        ⏳
   
   ENVIO          RETORNO PREVISTO     RETORNO REAL
   10/12/2025     20/12/2025           [Aguardando]
   ```

3. Verifique:
   - [ ] Timeline visual renderizada
   - [ ] 3 pontos/etapas visíveis
   - [ ] Datas aparecendo corretamente
   - [ ] Cores dos pontos mudam conforme status
   - [ ] Fornecedor exibido
   - [ ] Botão "Atualizar Datas" visível

**Resultado Esperado:** ✅ Timeline renderizada corretamente

---

## ✅ Teste 7: Atualizar Datas de Rastreio

**Objetivo:** Testar modal de rastreio

**Passos:**

1. Na seção "Rastreio", clique "Atualizar Datas"

2. Modal abre com 4 campos:
   ```
   ├─ Data de Envio
   ├─ Data Retorno Prevista
   ├─ Data Retorno Real
   └─ Observações
   ```

3. Preencha:
   ```
   Data de Envio: 10/12/2025
   Data Retorno Real: 16/12/2025
   Observações: Item retornou do laboratório
   ```

4. Clique "Atualizar"

5. Verifique:
   - [ ] Dados foram salvos
   - [ ] Timeline atualiza visualmente
   - [ ] Status muda se data_retorno foi preenchida

**Resultado Esperado:** ✅ Timeline e status atualizados

---

## ✅ Teste 8: Verificar Substituição/Aquisição

**Objetivo:** Testar seção de aquisição

**Passos:**

1. Expanda "Substituições / Aquisições"

2. Procure por card:
   ```
   Cotação SOL-2025-0005 - [Supplier XYZ] - Status
   ├─ Tipo: [Aquisição] 🟠
   ├─ Prazo: 5 dias
   ├─ Valor: R$ 1.500,00
   ├─ Data Prevista: 25/12/2025
   ├─ Data Chegada: [Pendente]
   └─ [Ver Solicitação] [Marcar Recebimento]
   ```

3. Verifique:
   - [ ] Card exibido corretamente
   - [ ] Tipo marcado como "Aquisição"
   - [ ] Botão "Marcar Recebimento" visível

**Resultado Esperado:** ✅ Card de aquisição visível

---

## ✅ Teste 9: Registrar Chegada de Aquisição

**Objetivo:** Testar modal de chegada

**Passos:**

1. Clique "Marcar Recebimento"

2. Modal abre:
   ```
   ╔═══════════════════════════════════╗
   ║ Registrar Data de Chegada         ║
   ╠═══════════════════════════════════╣
   ║ Data de Chegada *     [22/12/2025]║
   ║ Observações           [...]       ║
   ╠═══════════════════════════════════╣
   ║          [Cancelar] [Registrar]   ║
   ╚═══════════════════════════════════╝
   ```

3. Preencha:
   ```
   Data de Chegada: 22/12/2025
   Observações: Item recebido em perfeito estado
   ```

4. Clique "Registrar"

5. Verifique:
   - [ ] Dados salvos
   - [ ] Card mostra data de chegada
   - [ ] Status muda para "Recebido"
   - [ ] Página redireciona

**Resultado Esperado:** ✅ Chegada registrada, status atualizado

---

## ✅ Teste 10: Validação de Campo Obrigatório

**Objetivo:** Testar que data é obrigatória

**Passos:**

1. Abra modal de "Atualizar Data" (Calibração)

2. Limpe o campo "Data Realizada" completamente

3. Deixe vazio e clique "Atualizar"

4. Verifique:
   - [ ] Browser mostra validação HTML5
   - [ ] Mensagem: "Este campo é obrigatório"
   - [ ] OU: Submit não funciona

**Resultado Esperado:** ✅ Validação funciona

---

## ✅ Teste 11: Atualização de Status Automático

**Objetivo:** Testar que status atualiza automaticamente

**Passos:**

1. Anote o status atual da solicitação

2. Atualize dados em um atendimento (calibração, rastreio ou chegada)

3. Volte para a solicitação

4. Verifique:
   - [ ] Status mudou (se aplicável)
   - [ ] Mudança é consistente com as datas preenchidas
   - [ ] Não houve erro no console

**Resultado Esperado:** ✅ Status atualiza corretamente

---

## ✅ Teste 12: Responsividade Mobile

**Objetivo:** Testar layout em smartphone

**Passos:**

1. Abra DevTools (F12)

2. Ative "Device Toolbar" (Ctrl+Shift+M)

3. Selecione smartphone (ex: iPhone 12)

4. Navegue para `/instrumento/1/detalhes/`

5. Expanda "Cotações"

6. Verifique:
   - [ ] Cards em full width
   - [ ] Texto legível
   - [ ] Modals adaptados
   - [ ] Botões clicáveis
   - [ ] Sem scroll horizontal

**Resultado Esperado:** ✅ Layout responsivo em mobile

---

## 🐛 Testes de Erro

### Teste E1: Data Inválida

```
Ação: Colocar 31/02/2025 (data inválida)
Esperado: ❌ Validação HTML5 rejeita
```

### Teste E2: Campo Vazio

```
Ação: Deixar "Data Realizada" vazio
Esperado: ❌ Validação exigida
```

### Teste E3: Múltiplos Cliques

```
Ação: Clicar "Atualizar" 2x rapidamente
Esperado: ✅ Apenas 1 submit (sem duplicatas)
```

### Teste E4: Sem Cotações

```
Instrumento sem cotações
Ação: Abrir aba "Cotações"
Esperado: Alert "Nenhuma cotação pendente"
```

---

## 📊 Teste de Performance

### Teste P1: Load Time

```bash
# Medir tempo de carregamento
Time: Ctrl+Shift+I → Network → XHR
Esperado: < 500ms para página
Esperado: < 100ms para cada requisição
```

### Teste P2: Modal Response

```
Ação: Abrir modal
Esperado: < 100ms (imperceptível)
```

### Teste P3: Submit Response

```
Ação: Submeter formulário
Esperado: < 1s (com redireciona)
```

---

## ✨ Teste Visual

### Cores

- ✅ Verde: Status concluído
- ⏳ Amarelo: Em progresso
- ⏱️ Cinza: Pendente
- 🔴 Vermelho: Cotações (badge)

### Icons

- 📜 Certificados
- 📋 Cotações
- 🚚 Rastreio
- ⚠️ Ocorrências
- ✅ Sucesso
- ⏳ Carregando

---

## 🎯 Resultado Final

Se todos os testes passarem:

```
┌─────────────────────────────┐
│ ✅ TESTES COMPLETOS         │
│                             │
│ Checklist:                  │
│ ✓ 12 testes funcionais      │
│ ✓ 4 testes de erro          │
│ ✓ 3 testes de performance   │
│ ✓ Responsividade OK         │
│                             │
│ Status: 🟢 PRONTO           │
│ Recomendação: PRODUÇÃO      │
│                             │
└─────────────────────────────┘
```

---

## 📝 Template de Relatório

```markdown
# Teste de Integração - 16/12/2025

## Ambiente
- Navegador: Chrome 131
- Resolução: 1920x1080
- Servidor: Django dev
- BD: SQLite

## Resultados

### Testes Funcionais
- [ ] Aba "Cotações" visível
- [ ] 3 seções exibem corretamente
- [ ] Modals abrem/fecham
- [ ] Dados salvam corretamente
- [ ] Status atualiza automaticamente

### Testes Responsividade
- [ ] Desktop (1920px): OK
- [ ] Tablet (768px): OK
- [ ] Mobile (375px): OK

### Testes Performance
- [ ] Load: 450ms ✓
- [ ] Modal: 50ms ✓
- [ ] Submit: 800ms ✓

### Issues Encontrados
- Nenhum

## Conclusão
✅ Pronto para produção

Assinado:
Data: 16/12/2025
```

---

**Tempo total estimado:** 30-45 minutos  
**Dificuldade:** Fácil  
**Requisitos:** Apenas acesso ao sistema

