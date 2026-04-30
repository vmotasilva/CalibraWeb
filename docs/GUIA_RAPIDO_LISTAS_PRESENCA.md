# Guia Rápido - Sistema de Listas de Presença

## Como Acessar

1. No menu principal, clique em **"Treinamentos"**
2. Selecione **"Listas de Presença"** no dropdown

## Método 1: Criar Lista Manualmente

### Passo a Passo

1. **Clique em "Nova Lista"**
   
2. **Preencha as Informações da Sessão:**
   - Título: Nome da sessão de treinamento
   - Data da Sessão: Quando ocorreu
   - Instrutor: Quem ministrou (selecione da lista)
   - Horário: Início e fim (opcional)
   - Carga Horária: Em horas (opcional)
   - Local: Onde ocorreu (opcional)
   - Observações: Notas adicionais (opcional)

3. **Adicione os Participantes:**
   - Para cada participante, clique em "Adicionar Registro"
   - Selecione o Colaborador
   - Selecione o Procedimento que foi treinado
   - Data do Treinamento (deixe vazio para usar a data da sessão)
   - Observações (opcional)

4. **Salve**
   - O sistema gera automaticamente um código único (ex: LP2025-0001)
   - Todos os registros ficam vinculados a esta lista

### Vantagens
✅ Total controle dos dados
✅ Pode adicionar/remover participantes facilmente
✅ Visualização imediata

## Método 2: Importar em Massa via Excel

### Passo a Passo

1. **Baixe o Template**
   - Na página de Listas de Presença, clique em "Importar"
   - Clique em "Baixar Template"
   - Um arquivo Excel será baixado

2. **Preencha o Template**
   
   **Colunas Obrigatórias:**
   - `matricula`: Matrícula do colaborador (ex: 123456)
   - `procedimento_codigo`: Código do procedimento (ex: PO-001)
   - `data_treinamento`: Data no formato AAAA-MM-DD (ex: 2025-01-15)
   
   **Colunas Opcionais (para agrupamento automático):**
   - `instrutor_matricula`: Matrícula do instrutor
   - `hora_inicio`: Hora início (ex: 08:00)
   - `hora_fim`: Hora fim (ex: 12:00)
   - `local`: Local do treinamento
   - `titulo`: Título da sessão
   - `observacoes`: Observações

3. **Faça o Upload**
   - Volte à página "Importar"
   - Selecione o arquivo Excel preenchido
   - **IMPORTANTE:** Marque a opção "Agrupar em listas de presença automaticamente"
   - Se quiser sobrescrever registros duplicados, marque a opção

4. **Clique em "Importar Arquivo"**
   - O sistema processa os dados
   - Valida colaboradores e procedimentos
   - Detecta automaticamente treinamentos da mesma sessão
   - Cria listas de presença agrupando por: data + instrutor + horário

5. **Revise os Resultados**
   - Veja quantos registros foram criados
   - Quantas listas foram geradas automaticamente
   - Se houve erros, eles serão listados com número da linha

### Exemplo Prático

Imagine que você tem este Excel:

| matricula | procedimento_codigo | data_treinamento | instrutor_matricula | hora_inicio | hora_fim | local  | titulo            |
|-----------|---------------------|------------------|---------------------|-------------|----------|--------|-------------------|
| 123456    | PO-001             | 2025-01-15      | 789012             | 08:00      | 12:00   | Sala A | Treinamento PO-001 |
| 123457    | PO-001             | 2025-01-15      | 789012             | 08:00      | 12:00   | Sala A | Treinamento PO-001 |
| 123458    | PO-002             | 2025-01-15      | 789012             | 14:00      | 18:00   | Lab B  | Treinamento PO-002 |

**Resultado:**
- **2 listas de presença criadas:**
  - Lista 1 (LP2025-0001): 2 registros (matrícula 123456 e 123457 - mesma sessão)
  - Lista 2 (LP2025-0002): 1 registro (matrícula 123458 - sessão diferente)

### Vantagens
✅ Processar centenas de registros de uma vez
✅ Agrupamento automático por sessão
✅ Ideal para importar histórico antigo
✅ Reduz trabalho manual

## Visualizar e Gerenciar

### Ver Lista
- Clique no botão "Ver" no card da lista
- Veja todos os detalhes:
  - Informações da sessão
  - Total de participantes
  - Total de procedimentos
  - Tabela completa de registros

### Editar Lista
- Clique no botão "Editar"
- Modifique informações da sessão
- Adicione ou remova registros
- Salve as alterações

### Exportar PDF
- Clique no botão "PDF"
- Um PDF será gerado com:
  - Cabeçalho com dados da sessão
  - Tabela de participantes com espaço para assinatura
- Use para coleta de assinaturas físicas

### Excluir Lista
- Clique no botão "Excluir" (ícone lixeira)
- Confirme a exclusão
- ⚠️ **ATENÇÃO:** Todos os registros vinculados também serão excluídos!

## Como o Agrupamento Automático Funciona

O sistema agrupa registros na mesma lista de presença quando eles têm:
- ✅ Mesma data de treinamento
- ✅ Mesmo instrutor
- ✅ Mesmo horário (início e fim)
- ✅ Mesmo local
- ✅ Mesmo título

Se **qualquer um** destes campos for diferente, o sistema cria uma nova lista.

## Dicas e Boas Práticas

### Para Criação Manual:
1. Use nomes descritivos nos títulos (ex: "Treinamento Inicial PO-001")
2. Sempre preencha o instrutor para rastreabilidade
3. Adicione observações relevantes
4. Exporte PDF logo após criar para arquivamento

### Para Importação em Massa:
1. **Sempre** baixe e use o template fornecido
2. Use formato de data AAAA-MM-DD (Excel pode mudar automaticamente!)
3. Confira matrículas e códigos antes de importar
4. Teste primeiro com poucos registros
5. Certifique-se que todos os colaboradores já estão cadastrados no sistema
6. Certifique-se que todos os procedimentos já existem

### Para Agrupamento Correto:
1. Mantenha **exatamente os mesmos valores** para treinamentos da mesma sessão:
   - Mesmo instrutor_matricula
   - Mesma hora_inicio
   - Mesma hora_fim
   - Mesmo local
   - Mesmo titulo
2. Qualquer diferença (mesmo um espaço extra) criará lista separada

## Resolução de Problemas

### Erro: "Colaborador não encontrado"
- Verifique se a matrícula está correta
- Confirme se o colaborador existe no sistema (menu RH → Colaboradores)
- Matriculas são case-sensitive

### Erro: "Procedimento não encontrado"
- Verifique se o código está correto (ex: PO-001)
- Confirme se o procedimento existe (menu Procedures → Procedimentos)
- Códigos são case-sensitive

### Importação criou muitas listas separadas
- Revise os campos de agrupamento no Excel
- Certifique-se que registros da mesma sessão têm valores **idênticos**
- Copie e cole valores em vez de digitar para evitar diferenças sutis

### Registros duplicados
- O sistema detecta duplicatas por: colaborador + procedimento + data
- Use a opção "Sobrescrever existentes" para atualizar
- Ou desmarque para ignorar duplicatas

## Exemplo Completo de Uso

### Cenário: Treinamento de Qualidade - 15/01/2025

**Situação:** 
- 20 colaboradores participaram
- 3 procedimentos foram treinados
- Instrutor: João Silva (matrícula 789012)
- Local: Sala de Treinamento A
- Horário: 08:00 às 12:00

**Método Recomendado: Importação Excel**

1. Baixar template
2. Preencher 60 linhas (20 colaboradores × 3 procedimentos):
   - Todas com mesma data: 2025-01-15
   - Todas com mesmo instrutor: 789012
   - Todas com mesmo horário: 08:00 - 12:00
   - Todas com mesmo local: Sala de Treinamento A
   - Todas com mesmo título: Treinamento de Qualidade
3. Importar arquivo
4. Sistema cria 1 única lista (LP2025-0001) com 60 registros
5. Acessar lista e exportar PDF
6. Imprimir e coletar assinaturas

**Resultado:** 
- ✅ 60 registros criados em segundos
- ✅ 1 lista de presença organizada
- ✅ PDF pronto para assinaturas
- ✅ Dados rastreáveis e auditáveis

## Recursos do Sistema

### Código Auto-Gerado
- Formato: LP + ANO + NÚMERO (4 dígitos)
- Exemplo: LP2025-0001, LP2025-0002, etc.
- Reinicia a cada ano
- Único e não editável

### Estatísticas
- Total de participantes (distintos)
- Total de procedimentos (distintos)
- Total de registros (pode haver repetições se um colaborador treinou múltiplos procedimentos)

### Integração
- Vinculado ao módulo RH (colaboradores)
- Vinculado ao módulo Procedures (procedimentos)
- Registros aparecem na matriz de treinamento do colaborador
- Contabilizado para validade de treinamentos

### Auditoria
- Registra quem criou cada lista
- Data/hora de criação
- Data/hora de última atualização

## Próximos Passos

Após criar suas listas de presença:
1. Verifique a matriz de treinamento dos colaboradores
2. Os treinamentos aparecerão com status "OK" ou "PENDENTE"
3. Use o Dashboard de Gaps para análise
4. Planeje próximos treinamentos baseado nas deficiências

---

**Precisa de Ajuda?**
- Acesse a documentação completa: `SISTEMA_LISTAS_PRESENCA.md`
- Contate o suporte técnico
- Consulte o departamento de qualidade
