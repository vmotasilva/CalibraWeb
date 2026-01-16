# 📊 Exportação de Planejamentos para Excel

## Visão Geral

O CalibraWEB agora permite exportar informações de planejamentos de treinamento para arquivos Excel, tanto da lista completa quanto dos detalhes de um planejamento específico.

## 🎯 Funcionalidades

### 1. Exportar Lista de Planejamentos

**Local**: Tela de Planejamentos (Lista)

**O que é exportado**:
- ID do planejamento
- Título
- Status (Planejado, Confirmado, Realizado, Cancelado)
- Origem (Procedimento, Matriz, Demanda, Livre)
- Data prevista
- Data realizada
- Instrutor responsável
- Carga horária
- Procedimentos associados
- Colaboradores participantes
- Local
- Observações

**Como usar**:
1. Acesse: **Planejamento de Treinamentos**
2. Aplique filtros desejados (opcional)
3. Clique em **"Exportar Excel"** (botão verde no canto superior direito)
4. O arquivo será baixado automaticamente como `planejamentos_lista.xlsx`

**Exemplo de URL**:
```
/procedures/planejamentos/export/lista-excel/?status=PLANEJADO&instrutor=5
```

---

### 2. Exportar Detalhes de um Planejamento

**Local**: Tela de Detalhes do Planejamento

**O que é exportado** (em múltiplas abas):

#### Aba 1: Informações
- ID
- Título
- Status
- Origem
- Datas (prevista, realizada)
- Horários
- Instrutor
- Local
- Carga horária
- Descrição
- Observações

#### Aba 2: Procedimentos
- Código do procedimento
- Nome
- Descrição
- Disciplina(s) associada(s)

#### Aba 3: Colaboradores
- Nome completo
- Matrícula
- Cargo
- Setor
- Status (Ativo/Inativo)

#### Aba 4: Registros de Treinamento
- Colaborador
- Procedimento
- Data do treinamento
- Hora do treinamento
- Status (Concluído/Pendente)

**Como usar**:
1. Acesse: **Planejamento de Treinamentos** → Clique em um planejamento
2. Clique em **"Exportar Excel"** (botão verde na barra superior)
3. O arquivo será baixado automaticamente como `planejamento_{ID}.xlsx`

**Exemplo de URL**:
```
/procedures/planejamentos/42/export/excel/
```

---

## 🛠️ Detalhes Técnicos

### Arquitetura

```
procedures/
├── views/
│   └── planejamento_views.py          # Views de export
├── utils/
│   └── export_utils.py                # Classe PlanejamentoExcelExporter
├── templates/
│   ├── planejamento_lista.html        # Botão de export lista
│   └── planejamento_detalhe.html      # Botão de export detalhe
└── urls.py                             # Rotas de export
```

### Views Criadas

#### `exportar_lista_planejamentos_excel_view(request)`
- **Rota**: `procedures:exportar_lista_planejamentos_excel`
- **URL**: `/procedures/planejamentos/export/lista-excel/`
- **Método**: GET
- **Parâmetros**: Herda filtros da URL (q, status, instrutor, etc.)
- **Retorno**: HttpResponse com arquivo `.xlsx`

#### `exportar_detalhe_planejamento_excel_view(request, planejamento_id)`
- **Rota**: `procedures:exportar_detalhe_planejamento_excel`
- **URL**: `/procedures/planejamentos/<id>/export/excel/`
- **Método**: GET
- **Parâmetros**: `planejamento_id` (inteiro)
- **Retorno**: HttpResponse com arquivo `.xlsx` (múltiplas abas)

### Classe Exportadora

**`PlanejamentoExcelExporter`** (procedures/utils/export_utils.py)

Métodos principais:
- `export_lista_planejamentos(planejamentos)` - Exporta lista filtrada
- `export_detalhe_planejamento(planejamento)` - Exporta detalhes com múltiplas abas
- `_auto_adjust_columns(ws)` - Ajusta largura de colunas automaticamente

---

## 📋 Exemplo de Uso Prático

### Cenário 1: Exportar todos os planejamentos de um instrutor

1. Acesse: **Planejamento de Treinamentos**
2. No filtro "Instrutor", selecione: **"João Silva"**
3. Clique em **"Filtrar"**
4. Clique em **"Exportar Excel"**
5. Arquivo baixado: `planejamentos_lista.xlsx` (apenas de João Silva)

### Cenário 2: Exportar detalhes completos do treinamento

1. Acesse: **Planejamento de Treinamentos**
2. Clique em um planejamento específico (ex: "Treinamento de Corte MEI")
3. Clique em **"Exportar Excel"** (botão verde)
4. Arquivo baixado: `planejamento_42.xlsx` (com 4 abas de dados)

---

## 💾 Formatos de Arquivo

### Arquivo Excel Gerado

- **Formato**: `.xlsx` (Excel 2007+)
- **Compatibilidade**: Microsoft Excel, Google Sheets, LibreOffice
- **Tamanho**: Típico 50-500 KB (depende da quantidade de dados)
- **Encoding**: UTF-8

### Formatação

- **Cabeçalhos**: Fundo azul (#0D6EFD) com texto branco
- **Bordas**: Todas as células têm bordas finas para melhor visualização
- **Quebra de texto**: Ativada automaticamente
- **Congelamento**: Primeira linha congelada (múltiplas abas)
- **Largura**: Colunas ajustadas automaticamente

---

## 🔒 Segurança

- **Autenticação**: Apenas usuários logados podem exportar
- **Filtros aplicados**: Export respeita os filtros da interface
- **Dados sensíveis**: Mostra apenas dados que o usuário tem acesso
- **Rate limiting**: Não há limite, mas downloads são registrados em logs

---

## 📊 Casos de Uso

1. **Relatórios Executivos**: Exportar lista de planejamentos por período
2. **Auditoria**: Exportar detalhes completos com registros de treinamento
3. **Integração**: Importar em sistemas de gestão (SAP, BI, etc)
4. **Análise**: Usar dados em Excel para criar gráficos customizados
5. **Comunicação**: Compartilhar planejamentos por email

---

## ⚠️ Limitações

- **Tamanho máximo**: Até 1.048.576 linhas por aba (limite Excel)
- **Procedimentos/Colaboradores**: Mostrados em células concatenadas
- **Imagens**: Não são exportadas (apenas URLs/referências)
- **Formatação HTML**: Não é mantida nas observações/descrições

---

## 🐛 Troubleshooting

### Problema: "Botão de export não aparece"
**Solução**: 
- Verifique se está logado
- Limpe cache do navegador (Ctrl + Shift + Delete)
- Verifique permissões de acesso

### Problema: "Erro ao baixar arquivo"
**Solução**:
- Tente em outro navegador
- Desative ad-blocker
- Verifique espaço em disco

### Problema: "Caracteres especiais aparecem como ?"
**Solução**:
- Arquivo está em UTF-8
- Abra com: Excel → Dados → Origem de Dados → Codificação UTF-8

---

## 📝 Próximas Melhorias

- [ ] Exportar para PDF (relatório visual)
- [ ] Exportar para CSV (integração com SIS)
- [ ] Template customizável para export
- [ ] Agendamento de exports automáticos
- [ ] Export com gráficos embutidos

---

**Versão**: 1.0  
**Data de Criação**: Janeiro 2026  
**Status**: ✅ Produção
