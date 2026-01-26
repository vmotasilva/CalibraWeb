# 🎯 GUIA RÁPIDO: Históricos de Calibração

## ✨ O que foi implementado

Um novo link na barra de navegação para visualizar todos os históricos de calibração da empresa com filtros avançados.

## 📍 Onde encontrar

1. **Navegação Principal** → Clique em **"Metrologia"** (dropdown)
2. Na lista de opções, clique em **"Históricos de Calibração"** (novo link)
3. Ou acesse diretamente: `/metrologia/historicos/`

```
Metrologia
├── Dashboard Metrologia
├── Lista de Instrumentos
├── ✨ Históricos de Calibração (NOVO!)
├── Categorias
├── Unidades de Medida
├── Solicitações de Cotação
└── Importação
   ├── Importar Instrumentos
   └── Importar Histórico
```

## 📊 O que você vê na tela

### Seção 1: Filtros (Parte Superior)
```
┌─────────────────────────────────────────────────────────┐
│ Buscar              │ Status    │ Resultado │ Tipo │...  │
│ [texto livre]       │ [dropdown]│ [dropdown]│ [DD] │     │
│                     │           │           │      │Filtro│
└─────────────────────────────────────────────────────────┘
```

**Filtros disponíveis:**
- **Buscar**: Por instrumento, código, certificado ou fornecedor
- **Status**: Vigentes, A Vencer (30 dias), Vencidas
- **Resultado**: Aprovado, Aprovado c/ Correção, Reprovado
- **Tipo**: Externa, Interna
- **Categoria**: Filtro por categoria do instrumento

### Seção 2: Tabela de Resultados
```
┌─────────────────────────────────────────────────────────────────┐
│ Total: 150 históricos                                           │
├─────────────────────────────────────────────────────────────────┤
│ Instrumento │ Categ. │ Data Cal. │ Próx. Cal. │ Status │...    │
├─────────────────────────────────────────────────────────────────┤
│ IN-001      │ [badge]│ 01/01/26  │ 01/01/27   │ Verde  │...    │
│ IN-002      │ [badge]│ 15/12/25  │ 15/12/26   │ Vermelho│...   │
│ IN-003      │ [badge]│ 20/11/25  │ 20/11/26   │ Amarelo│...    │
│ ...         │ ...    │ ...       │ ...        │ ...    │...    │
└─────────────────────────────────────────────────────────────────┘
```

**Colunas exibidas:**
- 📦 **Instrumento**: Nome e descrição (clicável)
- 🏷️ **Categoria**: Badge colorido
- 📅 **Data Calibração**: Data da última calibração
- ⏰ **Próxima Calibração**: Com indicador visual de status
- ✅ **Status**: Vencido/Vigente
- 📋 **Resultado**: Aprovado/Reprovado
- 🔄 **Tipo**: Externa/Interna
- 📄 **Certificado**: Link para download (se houver)
- ⚙️ **Ações**: Botão para ver detalhes

## 🎨 Indicadores Visuais

| Badge | Significado | Cor |
|-------|-------------|-----|
| Vencido | Calibração vencida | 🔴 Vermelho |
| Vigente | Calibração vigente | 🟢 Verde |
| A vencer | Vence em até 30 dias | 🟡 Amarelo |
| Aprovado | Passou na calibração | 🔵 Azul |
| Reprovado | Falhou na calibração | 🔴 Vermelho |
| Externa | Calibração por fornecedor | 🔵 Azul |
| Interna | Calibração própria | ⚫ Cinza |

## 🔍 Exemplos de Uso

### Caso 1: Encontrar instrumentos com calibração vencida
1. Na seção de Filtros, selecione:
   - **Status**: "Vencidas"
2. Clique em **Filtrar**
3. A tabela mostrará apenas históricos vencidos

### Caso 2: Buscar um instrumento específico
1. Na seção de Filtros, no campo **Buscar**, digite:
   - Código do instrumento (ex: "IN-001")
   - Tag (ex: "PAQUÍMETRO")
   - Número do certificado (ex: "CERT-2026-001")
2. Clique em **Filtrar**
3. Resultados filtrados aparecem

### Caso 3: Ver todos os instrumentos aprovados de uma categoria
1. Selecione:
   - **Resultado**: "Aprovado"
   - **Categoria**: "Paquímetro" (exemplo)
2. Clique em **Filtrar**

## 📑 Navegação de Páginas

A tabela exibe 50 históricos por página. Use os botões de navegação:
- **Primeira** - Vai para a primeira página
- **Anterior** - Página anterior
- **Próxima** - Próxima página
- **Última** - Última página

Exemplo: "Página 2 de 15"

## 🔗 Interações Disponíveis

- **Clique no nome do instrumento** → Abre detalhes do instrumento
- **Clique no ícone de PDF** → Download do certificado
- **Clique no botão de olho** → Ver detalhes do histórico
- **Limpar** → Volta aos filtros padrão (todos os históricos)

## 💡 Dicas Úteis

1. **Use a busca** para encontrar rapidamente um instrumento
2. **Combine filtros** para resultados mais específicos
3. **Verifique regularmente** instrumentos "A vencer"
4. **Baixe certificados** diretamente da tabela
5. **Imprima a página** para gerar relatórios (Ctrl+P ou Cmd+P)

## 📈 Dados em Tempo Real

Os dados são carregados diretamente do banco de dados, então:
- ✅ Sempre atualizado
- ✅ Reflete mudanças imediatas
- ✅ Otimizado para performance
- ✅ Paginação eficiente

---

**Implementação:** 09/01/2026 | **Status:** ✅ Completo
