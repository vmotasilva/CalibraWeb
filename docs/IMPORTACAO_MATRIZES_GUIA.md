# Importação em Massa - Matrizes de Habilidades

## 📋 Visão Geral

O sistema de **Importação em Massa de Matrizes de Habilidades** permite que você importe múltiplas matrizes, disciplinas e colaboradores associados de uma única vez, economizando tempo e esforço.

## ✨ Características

- ✅ **Importação de Matrizes** - Crie múltiplas matrizes de habilidades
- ✅ **Importação de Disciplinas** - Adicione disciplinas associadas às matrizes
- ✅ **Associação de Colaboradores** - Vincule colaboradores às matrizes automaticamente
- ✅ **Suporte a CSV e Excel** - Escolha o formato que preferir
- ✅ **Validação Automática** - Sistema detecta e relata erros
- ✅ **Relatório Detalhado** - Visualize resultado completo da importação
- ✅ **Atualização de Existentes** - Atualize registros duplicados automaticamente

## 🚀 Como Usar

### 1. Acessar a Tela de Importação

1. Vá para **Procedimentos** → **Matrizes de Habilidades**
2. Clique no botão verde **"Importação em Massa"**

### 2. Escolher o Formato

Você pode escolher entre dois formatos:

#### **CSV (Arquivo de Texto)**
- Simples e rápido de criar
- Linhas separadas por `|` (pipe)
- Abra em qualquer editor de texto
- Compatível com Excel

#### **Excel (.xlsx)**
- Melhor formatação visual
- Múltiplas planilhas
- Validação integrada
- Mais fácil de revisar

### 3. Baixar o Template

Clique em um dos botões para baixar o template pré-formatado:
- **Template CSV** - Arquivo de texto
- **Template Excel** - Planilha formatada

### 4. Preencher o Template

#### Colunas Esperadas:

| Coluna | Descrição | Obrigatório | Exemplo |
|--------|-----------|------------|---------|
| **Matriz Código** | Código único da matriz | Sim | `MAT001` |
| **Matriz Nome** | Nome descritivo da matriz | Sim | `Operação` |
| **Disciplina Código** | Código da disciplina | Não | `DISC001` |
| **Disciplina Nome** | Nome da disciplina | Sim | `Segurança` |
| **Disciplina Descrição** | Descrição detalhada | Não | `Procedimentos...` |
| **Disciplina Prioridade** | Nível (Alta, Média, Baixa) | Não | `Alta` |
| **Disciplina Obrigatoriedade** | Requisito legal/padrão | Não | `NR 12, ISO 9001` |
| **Colaborador Matrícula** | Matrícula do colaborador | Não | `MAT001` |
| **Colaborador Nome** | Nome completo | Não | `João Silva` |
| **Colaborador Email** | Email do colaborador | Não | `joao@empresa.com` |

#### Exemplo de Dados:

```
Matriz Código|Matriz Nome|Disciplina Código|Disciplina Nome|Disciplina Descrição|Disciplina Prioridade|Disciplina Obrigatoriedade|Colaborador Matrícula|Colaborador Nome|Colaborador Email
MAT001|Operação|DISC001|Segurança|Procedimentos de segurança|Alta|NR 12|MAT001|João Silva|joao@empresa.com
MAT001|Operação|DISC002|Qualidade|Controle de qualidade|Alta|ISO 9001|MAT002|Maria Santos|maria@empresa.com
MAT002|Manutenção|DISC003|Manutenção Preventiva|Procedimentos de manutenção|Média|NR 12|MAT003|Pedro Costa|pedro@empresa.com
```

### 5. Fazer Upload do Arquivo

1. Clique na **área de drag-and-drop** ou selecione manualmente
2. O sistema validará o arquivo
3. Marque "Atualizar registros existentes" se desejar (opcional)
4. Clique em **"Processar Importação"**

### 6. Revisar Resultados

Após o processamento, você verá:

- **Resumo Estatístico** - Quantidade de registros criados/atualizados
- **Erros** - Linhas que não foram processadas
- **Avisos** - Problemas que não impediram a importação
- **Botões de Ação** - Ver matrizes ou fazer nova importação

## 📊 Formato CSV Detalhado

### Estrutura
```
[Coluna 1]|[Coluna 2]|[Coluna 3]|...
```

**Separador:** Pipe `|` (não use vírgula ou ponto-e-vírgula)

### Exemplo Completo
```csv
Matriz Código|Matriz Nome|Disciplina Código|Disciplina Nome|Disciplina Descrição|Disciplina Prioridade|Disciplina Obrigatoriedade|Colaborador Matrícula|Colaborador Nome|Colaborador Email
MAT001|Operação|DISC001|Segurança|Procedimentos de segurança operacional|Alta|NR 12|MAT001|João da Silva|joao.silva@empresa.com
MAT001|Operação|DISC002|Qualidade|Controle de qualidade em processo|Alta|ISO 9001|MAT002|Maria Santos|maria.santos@empresa.com
MAT001|Operação|DISC003|Segurança|Uso de EPIs|Alta|NR 6|MAT001|João da Silva|joao.silva@empresa.com
MAT002|Manutenção|DISC004|Manutenção Preventiva|Procedimentos de manutenção preventiva|Média||MAT003|Pedro Costa|pedro.costa@empresa.com
MAT002|Manutenção|DISC005|Manutenção Corretiva|Procedimentos de manutenção corretiva|Média||MAT003|Pedro Costa|pedro.costa@empresa.com
```

## 📑 Formato Excel Detalhado

### Estrutura
- **Primeira linha:** Cabeçalhos das colunas
- **Linhas seguintes:** Dados
- **Colunas:** Mesmas do CSV

### Exemplo Visual

| Matriz Código | Matriz Nome | Disciplina Código | Disciplina Nome | ... |
|---|---|---|---|---|
| MAT001 | Operação | DISC001 | Segurança | ... |
| MAT001 | Operação | DISC002 | Qualidade | ... |
| MAT002 | Manutenção | DISC003 | Manutenção Preventiva | ... |

## ⚠️ Regras e Validações

### Matrizes
- **Código** é obrigatório e deve ser único
- Se um código já existe, será **atualizado** (se opção marcada)
- Nome é obrigatório

### Disciplinas
- **Nome** é obrigatório
- Se não fornecido, código é gerado automaticamente
- Uma disciplina é identificada por: **Matriz + Nome**
- Se disciplina duplicada existir, será **atualizada**

### Colaboradores
- Buscados por **matrícula** → **nome** → **email**
- Se não encontrado, será registrado como **aviso**
- Não impede a importação se colaborador não existir
- Será criada associação se colaborador for encontrado

## 🔄 Lógica de Duplicação

### Identificação de Matrizes Duplicadas
```
Matriz Código = MAT001 (único)
```
Se existe matriz com código `MAT001`, será **atualizada** (se habilitado)

### Identificação de Disciplinas Duplicadas
```
Matriz + Nome = MAT001 + "Segurança"
```
Se existe disciplina com mesma matriz e nome, será **atualizada** (se habilitado)

### Associação de Colaboradores
```
Matriz + Colaborador = Única por combinação
```
Não cria duplicatas de associação

## 📈 Exemplos de Uso

### Cenário 1: Criar Tudo do Zero
```csv
MAT001|Operação|DISC001|Segurança|Procedimentos|Alta|NR 12|MAT001|João|joao@empresa.com
MAT001|Operação|DISC002|Qualidade|Controle||ISO 9001|MAT002|Maria|maria@empresa.com
MAT002|Manutenção|DISC003|Manutenção|Preventiva|Média||MAT003|Pedro|pedro@empresa.com
```
**Resultado:** 2 matrizes, 3 disciplinas, 3 colaboradores associados

### Cenário 2: Adicionar Mais Disciplinas
```csv
MAT001|Operação|DISC004|Segurança Máquinas|Procedimentos|Alta|NR 12|MAT001|João|joao@empresa.com
MAT001|Operação|DISC005|Limpeza|Procedimentos|Média||MAT002|Maria|maria@empresa.com
```
**Resultado:** MAT001 e MAT002 existem, adicionam 2 novas disciplinas

### Cenário 3: Atualizar Informações
```csv
MAT001|Operação - Turno A|DISC001|Segurança|Nova descrição|Crítica|NR 12|MAT001|João|joao@empresa.com
```
**Resultado:** MAT001 nome atualizado, DISC001 descrição e prioridade atualizadas

## 🐛 Troubleshooting

### Erro: "Arquivo deve ser CSV ou Excel"
- Verifique a extensão do arquivo (.csv ou .xlsx)
- Não use .xls (versão antiga do Excel)

### Erro: "Cabeçalho não encontrado"
- Certifique-se de que a primeira linha contém os nomes das colunas
- Verifique se está usando os nomes exatos de coluna

### Aviso: "Colaborador não encontrado"
- O sistema procura por: matrícula → nome completo → email
- Verifique se o dados do colaborador estão corretos no sistema
- Você pode deixar em branco para não associar ninguém

### Erro: "Matriz código e nome são obrigatórios"
- Preecha obrigatoriamente: Matriz Código, Matriz Nome e Disciplina Nome
- As outras colunas podem ser deixadas em branco

## 💡 Dicas

1. **Comece Pequeno** - Faça um teste com 5-10 linhas antes de importar muitos dados
2. **Use o Template** - Sempre comece baixando o template fornecido
3. **Valide o Arquivo** - Abra em Excel e revise antes de enviar
4. **Crie Backup** - Faça backup antes de grandes importações
5. **Revise Resultados** - Sempre revise o relatório de importação
6. **Matrícula Padrão** - Se todos colaboradores usam matrícula, use esse campo

## 📞 Suporte

Se encontrar problemas:
1. Verifique o relatório de erros/avisos
2. Baixe o template novamente
3. Valide o formato do arquivo
4. Contacte o administrador do sistema

---

**Última atualização:** 2024  
**Versão:** 1.0
