# Unificação de Telas - Visualização e Edição

## Objetivo Alcançado
Unificação completa das telas de **visualização** e **edição** do Histórico de Calibração para ter o mesmo layout e estrutura visual.

## O Que Foi Feito

### 1. **Análise das Telas Originais**
- **Tela de Edição** (`editar_historico.html`): 1618 linhas com layout avançado de duas colunas
  - Coluna esquerda: Formulário de edição com dados editáveis, tabela de faixas, seção de padrões com upload
  - Coluna direita: Visualizador PDF com PDF.js, controles de zoom, funcionalidade de carimbo
  
- **Tela de Visualização** (`historico_calibracao_detail.html`): 511 linhas, layout simples incompatível
  - Layout apenas em uma coluna
  - Campos em modo leitura, mas estrutura diferente

### 2. **Conversão da Tela de Visualização**
O arquivo `historico_calibracao_detail.html` foi **completamente reescrito** baseado na estrutura do `editar_historico.html`:

#### Estrutura Final (Modo Visualização)
```
Layout: Duas Colunas (Grid Bootstrap 5)
├── Coluna Esquerda (col-lg-6)
│   ├── Seção: Dados do Histórico
│   │   ├── Data de Calibração (plaintext)
│   │   ├── Próxima Calibração (plaintext)
│   │   ├── Nº Certificado (plaintext)
│   │   ├── Tipo de Calibração (plaintext)
│   │   ├── Responsável (plaintext)
│   │   ├── Laboratório (plaintext)
│   │   └── Possui Selo RBC? (badge)
│   │
│   ├── Seção: Padrões de Calibração (colapsível)
│   │   └── Lista de padrões com download (sem upload/remoção)
│   │
│   ├── Seção: Observações (plaintext)
│   │
│   ├── Seção: Resultados de Medição por Faixa
│   │   └── Tabela: Faixa | Unidade | Tolerância | Erro | Incerteza | EMA | EME | Resultado
│   │           (SEM botões de edição/remoção)
│   │
│   └── Seção: Certificados Disponíveis
│       ├── Certificado Original (com botões: Visualizar, Download)
│       └── Certificado Carimbado (com botões: Visualizar, Download)
│
└── Coluna Direita (col-lg-6)
    ├── Visualizador PDF com PDF.js
    │   ├── Toolbar: Navegação de páginas, zoom
    │   └── Canvas: Renderização do PDF
    │
    └── Status do Certificado (se carimbado)
```

### 3. **Principais Alterações**

#### Removido (por ser específico de edição):
- ✅ Formulários de edição (`{{ historico_form.* }}`)
- ✅ Campo de upload de padrões
- ✅ Botões de remoção de padrões
- ✅ Botões de edição de faixas (Edit/Delete)
- ✅ Modais de edição de resultados
- ✅ Seção "Aplicar Carimbo" (SEÇÃO 4)
- ✅ Funcionalidade de clique em PDF para posicionar carimbo
- ✅ Scripts de manipulação de modais
- ✅ Scripts de AJAX para adicionar faixas

#### Mantido (comum a ambas):
- ✅ Layout de duas colunas com grid Bootstrap 5
- ✅ Seção de dados em modo leitura (plaintext)
- ✅ Seção de padrões colapsível (sem upload)
- ✅ Tabela de faixas de medição (visualização apenas)
- ✅ Seção de certificados disponíveis
- ✅ Visualizador PDF com PDF.js completo
- ✅ Estilos CSS idênticos
- ✅ Funcionalidade de visualização de diferentes certificados

### 4. **Características Mantidas**

#### Navegação de PDF
- Botões Previous/Next Page
- Indicador de página atual
- Controles de Zoom (In/Out) com percentual
- Renderização responsiva com PDF.js

#### Visualização de Certificados
- Possibilidade de visualizar certificado original
- Possibilidade de visualizar certificado carimbado
- Botões de download direto
- Preview simulado se PDF não disponível

#### Seção de Padrões
- Colapsível por padrão (status original mantido)
- Lista de padrões anexados
- Botões de download para cada padrão
- Indicador de quantidade de padrões

### 5. **Teste de Funcionalidade**

A tela agora apresenta:
- **URL**: `/metrologia/historico/{id}/visualizar/`
- **Botões de navegação**: 
  - "Voltar" → Volta para detalhe do instrumento
  - "Editar" → Vai para tela de edição
- **Layout**: Idêntico ao da tela de edição
- **Dados**: Todos em modo somente leitura (plaintext e badges)

## Resultado Final

As duas telas agora compartilham a **mesma estrutura visual e layout**, diferenciando-se apenas em:
- **Modo de Edição**: Campos como `<input>`, `<select>`, botões de ação (salvar, deletar)
- **Modo Visualização**: Campos como `<p class="form-control-plaintext">`, sem botões de ação

### Benefícios da Unificação:
✅ **Consistência visual** entre telas  
✅ **Mesma experiência de usuário** em ambos os modos  
✅ **Fácil manutenção** - estrutura única  
✅ **Navegação intuitiva** entre edição e visualização  
✅ **Responsive design** mantido em ambas  
✅ **Funcionalidades avançadas** (PDF viewer, zoom) disponíveis em ambas

## Próximos Passos Opcionais

Se desejado, podem ser implementados:
1. Single template com variable condicional `{% if modo_edicao %}` para reduzir duplicação
2. Template inheritance ou includes para reutilização de código
3. CSS classes condicionais para diferentes modos visuais
4. Botões flutuantes para ações (editar, remover) na visualização

## Arquivos Modificados

- `metrologia/templates/metrologia/historico_calibracao_detail.html` (completamente reescrito - 1221 linhas)
- Baseado em: `metrologia/templates/metrologia/editar_historico.html`

---
**Status**: ✅ CONCLUÍDO  
**Data**: 11/12/2025  
**Usuário**: Solicitação de unificação de telas
