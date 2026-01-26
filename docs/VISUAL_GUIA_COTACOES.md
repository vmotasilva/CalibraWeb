# 🎨 VISUAL: Cotações no Detalhamento de Instrumentos

## 📱 Novo Layout da Página

```
┌───────────────────────────────────────────────────────────────┐
│ DETALHAMENTO DE INSTRUMENTO                                   │
│ TH-15 - Micrômetro Digital                                    │
└───────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TABS:                                                           │
│ [📜 Certificados] [📋 Cotações🔴2] [🚚 Rastreio] [⚠️ Ocor...]│
└─────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════
                          ABA: COTAÇÕES
═══════════════════════════════════════════════════════════════════

┌─ 📋 REGISTROS DE CALIBRAÇÃO (1) ─────────────────────────────┐
│ ▼                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌──────────────────────────────────────────────────────────┐│
│ │ Cotação SOL-2025-0003 - [Tecnolab] - ✅ Concluído      ││
│ ├──────────────────────────────────────────────────────────┤│
│ │                                                          ││
│ │ Local: [No Local]    Prazo: 2 dias    Valor: R$ 250,00││
│ │ Data Prevista: 20/12/2025                              ││
│ │ Data Realizada: [16/12/2025] ✅                        ││
│ │ Técnico: João Silva                                     ││
│ │                                                          ││
│ │ [Ver Solicitação] [Atualizar Data]                     ││
│ └──────────────────────────────────────────────────────────┘│
│                                                              │
└──────────────────────────────────────────────────────────────┘

┌─ 🚚 RASTREIO EM LABORATÓRIO ────────────────────────────────┐
│ ▶ (recolhido)                                                │
└──────────────────────────────────────────────────────────────┘

┌─ ↩️ SUBSTITUIÇÕES / AQUISIÇÕES ──────────────────────────────┐
│ ▶ (recolhido)                                                │
└──────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
                    MODAL: ATUALIZAR CALIBRAÇÃO
═══════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────┐
│ ✕ Atualizar Data de Calibração                               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Data Realizada *                                             │
│  ┌──────────────────────────────────────┐                    │
│  │ 16/12/2025                           │ 📅                │
│  └──────────────────────────────────────┘                    │
│                                                                │
│  Técnico Responsável                                          │
│  ┌──────────────────────────────────────┐                    │
│  │ João Silva                           │                    │
│  └──────────────────────────────────────┘                    │
│                                                                │
│  Observações                                                  │
│  ┌──────────────────────────────────────┐                    │
│  │ Teste realizado com sucesso          │                    │
│  │                                      │                    │
│  └──────────────────────────────────────┘                    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                    [Cancelar]  [Atualizar ✓]                 │
└────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
               VISUAL: TIMELINE DE RASTREIO
═══════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────┐
│ Cotação SOL-2025-0004 - [TecnoMed] - ⏳ Em Laboratório      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Timeline de Rastreio:                                        │
│                                                                │
│  ●────────●────────●                                          │
│  ✅        ℹ️        ⏳                                          │
│                                                                │
│  ENVIO                RETORNO PREVISTO     RETORNO REAL      │
│  10/12/2025          20/12/2025            [Aguardando]      │
│                                                                │
│  Fornecedor: TecnoMed                                         │
│  Observações: Instrumento em processo de calibração           │
│                                                                │
│  [Atualizar Datas]  [Ver Solicitação]                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
           CARD: SUBSTITUIÇÃO/AQUISIÇÃO
═══════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────┐
│ Cotação SOL-2025-0005 - [Supplier XYZ] - ⏳ Aguardando      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Tipo: [Aquisição] 🟠                                         │
│  Prazo: 5 dias                                                │
│  Valor: R$ 1.500,00                                           │
│                                                                │
│  Data Prevista: 25/12/2025                                    │
│  Data de Chegada: [Pendente] 🟡                              │
│                                                                │
│  Detalhes: Novo micrômetro digital, marca XYZ, modelo ABC    │
│                                                                │
│  [Ver Solicitação]  [Marcar Recebimento]                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
        FLUXO: Antes vs Depois
═══════════════════════════════════════════════════════════════════

ANTES:
┌─────────────────────┐
│ Instrumento Detail  │
├─────────────────────┤
│ Tab 1: Certificados │
│ Tab 2: Rastreio     │
│ Tab 3: Ocorrências  │
│                     │
│ ❌ Cotações?       │
│ ❌ Datas atualiz?  │
└─────────────────────┘

DEPOIS:
┌──────────────────────────────────────┐
│ Instrumento Detail                   │
├──────────────────────────────────────┤
│ Tab 1: Certificados                  │
│ Tab 2: 📋 COTAÇÕES ✨ (NOVO!)        │
│   ├─ Registros de Calibração        │
│   ├─ Rastreio em Laboratório        │
│   └─ Substituições/Aquisições       │
│ Tab 3: Rastreio                      │
│ Tab 4: Ocorrências                   │
│                                      │
│ ✅ Todas as cotações em um lugar    │
│ ✅ Atualizar datas inline           │
│ ✅ Timeline visual                  │
│ ✅ Status automático                │
└──────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════
          STATUS BADGES E CORES
═══════════════════════════════════════════════════════════════════

Calibração:
  [✅ Concluído]  - Verde (status=CONCLUIDA, data_realizada preenchida)
  [⏳ Executando] - Amarelo (status=EXECUTANDO)
  [⏱️ Pendente]   - Cinza (status=PENDENTE)

Rastreio:
  [✅ Recebido]      - Verde (data_retorno preenchida)
  [⏳ Em Laboratório] - Amarelo (data_envio preenchida, data_retorno vazia)
  [⏱️ Aguardando]     - Cinza (nenhuma data preenchida)

Aquisição:
  [✅ Recebido]   - Verde (data_chegada preenchida)
  [⏱️ Aguardando]  - Cinza (data_chegada vazia)


═══════════════════════════════════════════════════════════════════
     RESPONSIVIDADE: Mobile vs Desktop
═══════════════════════════════════════════════════════════════════

DESKTOP (1024px+):
┌────────────────────────────────────────────────┐
│ Card com 2 colunas (left: info, right: dados) │
│ Timeline horizontal clara                     │
│ Modals com boa proporção                      │
└────────────────────────────────────────────────┘

TABLET (768px-1023px):
┌────────────────────────────────┐
│ Card com coluna única          │
│ Timeline centralizada          │
│ Modals adaptados               │
└────────────────────────────────┘

MOBILE (< 768px):
┌──────────────────┐
│ Card full-width  │
│ Timeline stack.  │
│ Modals grandes   │
│ Scroll horizontal│
└──────────────────┘


═══════════════════════════════════════════════════════════════════
         FEEDBACK VISUAL
═══════════════════════════════════════════════════════════════════

1. Ao abrir modal:
   ✨ Fade in com animação
   🎯 Foco automático no primeiro campo

2. Ao preencher:
   ✓ Validação em tempo real de datas

3. Ao clicar "Atualizar":
   ⏳ Loading implícito (redirect automático)

4. Após atualizar:
   ✅ Mensagem de sucesso
   📍 Volta para instrumento
   🔄 Dados visíveis e atualizados

5. Em caso de erro:
   ❌ Mensagem de erro
   📍 Volta para instrumento
   💡 Sugestão de ação


═══════════════════════════════════════════════════════════════════
      BADGE DE CONTAGEM NA ABA
═══════════════════════════════════════════════════════════════════

[📋 Cotações] ← Sem cotações
[📋 Cotações 🔴1] ← Uma cotação
[📋 Cotações 🔴3] ← Três cotações

Cor muda conforme contexto:
- Vermelho 🔴: Cotações pendentes
- Azul 🔵: Calibrações
- Amarelo 🟡: Em laboratório
- Verde 🟢: Completas


═══════════════════════════════════════════════════════════════════

