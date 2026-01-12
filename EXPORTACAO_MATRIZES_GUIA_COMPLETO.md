# 📊 EXPORTAÇÃO DE MATRIZES - GUIA COMPLETO

## 📍 Visão Geral

Sistema completo de exportação de Matrizes de Habilidades em **CSV** e **Excel**, permitindo extrair todos os dados (matrizes, disciplinas e colaboradores associados) para análise externa ou backup.

---

## 🚀 Como Usar

### Acessar a Tela de Matrizes

```
http://127.0.0.1:8000/procedures/matrizes/
```

### Botão de Exportação

Na barra superior da tela, você encontrará um botão amarelo **"Exportar"** com dropdown menu:

```
┌─────────────────┐
│ 📥 Exportar ▼   │
│  ├─ CSV         │
│  └─ Excel       │
└─────────────────┘
```

---

## 💾 Formatos Disponíveis

### 1️⃣ CSV (Comma Separated Values)

**Características:**
- ✅ Arquivo de texto puro
- ✅ Delimitador: `|` (pipe)
- ✅ Extensão: `.csv`
- ✅ Compatível com Excel, Google Sheets, Python Pandas
- ✅ Tamanho: Menor que Excel
- ✅ Aberto: Pode ser editado em qualquer editor de texto

**Quando usar:**
- Importação em outros sistemas
- Análise de dados em Python/Pandas
- Processamento em scripts
- Integração com aplicações
- Quando você prefere formato de texto

**Exemplo de conteúdo:**
```
Matriz Código|Matriz Nome|Matriz Descrição|Disciplina Código|Disciplina Nome|Disciplina Descrição|Colaborador Matrícula|Colaborador Nome|Colaborador Email
MAT001|Operação|Procedimentos de operação|DISC001|Segurança|Normas de segurança|MAT001|João Silva|joao@empresa.com
MAT001|Operação|Procedimentos de operação|DISC001|Segurança|Normas de segurança|MAT002|Maria Santos|maria@empresa.com
MAT001|Operação|Procedimentos de operação|DISC002|Qualidade|Controle de qualidade|MAT003|Pedro Oliveira|pedro@empresa.com
```

### 2️⃣ Excel (.xlsx)

**Características:**
- ✅ Arquivo binário formatado
- ✅ Extensão: `.xlsx`
- ✅ Compatível com Microsoft Excel, LibreOffice, Google Sheets
- ✅ Suporta estilos e formatação
- ✅ Cabeçalho congelado (primeira linha)
- ✅ Cores diferenciadas
- ✅ Borders nas células

**Quando usar:**
- Visualização profissional
- Compartilhamento com gestores/diretores
- Análise rápida em Excel
- Relatórios finais
- Apresentações
- Quando você prefere formato formatado

**Recursos de Formatação:**
- 🎨 Cabeçalho azul com texto branco
- 📌 Primeira linha congelada (não sai da tela ao rolar)
- 📊 Borders em todas as células
- 📐 Largura de colunas ajustada
- 🔤 Fonte legível
- ➡️ Alinhamento centralizado

---

## 📥 Baixar Arquivo

### Passos Rápidos

1. Acesse: `/procedures/matrizes/`
2. Clique no botão **"Exportar"**
3. Escolha:
   - **CSV** → Clique em "Exportar como CSV"
   - **Excel** → Clique em "Exportar como Excel"
4. Arquivo será baixado automaticamente
5. Abra com seu programa preferido

---

## 📋 Estrutura dos Dados

### Colunas Exportadas

| Coluna | Descrição | Exemplo |
|--------|-----------|---------|
| **Matriz Código** | Código único da matriz | MAT001 |
| **Matriz Nome** | Nome da matriz | Operação |
| **Matriz Descrição** | Descrição da matriz | Procedimentos operacionais |
| **Disciplina Código** | Código da disciplina | DISC001 |
| **Disciplina Nome** | Nome da disciplina | Segurança |
| **Disciplina Descrição** | Descrição da disciplina | Normas de segurança NR 12 |
| **Colaborador Matrícula** | Matrícula do colaborador | MAT001 |
| **Colaborador Nome** | Nome do colaborador | João Silva |
| **Colaborador Email** | Email do colaborador | joao@empresa.com |

### Exemplo de Dados Exportados

```
Matriz Código | Matriz Nome  | Disciplina Código | Colaborador Nome
MAT001        | Operação     | DISC001          | João Silva
MAT001        | Operação     | DISC001          | Maria Santos
MAT001        | Operação     | DISC002          | Pedro Oliveira
MAT002        | Manutenção   | DISC003          | Carlos Costa
```

---

## 🔍 Casos de Uso

### 1. Análise de Dados
```python
import pandas as pd

# Ler CSV exportado
df = pd.read_csv('exportacao_matrizes_20260112_095500.csv', sep='|')

# Filtrar por matriz
df_operacao = df[df['Matriz Código'] == 'MAT001']

# Contar colaboradores por disciplina
print(df.groupby('Disciplina Nome')['Colaborador Matrícula'].nunique())
```

### 2. Backup
- Exportar periodicamente em CSV
- Armazenar em pasta segura
- Manter histórico de mudanças

### 3. Compartilhamento com Gestores
- Exportar em Excel formatado
- Enviar por email
- Apresentar em reunião

### 4. Integração com Outros Sistemas
- Exportar em CSV
- Processar em script
- Importar em outro sistema

### 5. Relatório Executivo
- Exportar em Excel
- Adicionar gráficos
- Criar dashboard

---

## 📊 Nomenclatura dos Arquivos

Os arquivos exportados seguem padrão de nomenclatura com timestamp:

```
exportacao_matrizes_YYYYMMDD_HHMMSS.csv
exportacao_matrizes_YYYYMMDD_HHMMSS.xlsx
```

### Exemplos:
- `exportacao_matrizes_20260112_095500.csv`
- `exportacao_matrizes_20260112_095500.xlsx`

**Timestamp mostra quando foi feita a exportação:**
- YYYY = Ano (2026)
- MM = Mês (01)
- DD = Dia (12)
- HH = Hora (09)
- MM = Minuto (55)
- SS = Segundo (00)

---

## ✅ Dados Inclusos

### O que é Exportado:
✅ Todas as matrizes ativas e inativas
✅ Todas as disciplinas associadas
✅ Todos os colaboradores associados
✅ Descrições de cada item
✅ Código/nomenclatura de referência

### O que NÃO é Exportado:
❌ Histórico de avaliações
❌ Datas de criação/modificação
❌ Usuário que criou o registro
❌ Status de aprovação
❌ Comentários/notas internas

---

## 🔐 Segurança

**Dados Exportados:**
- Contêm informações sensíveis (emails, matrículas)
- Devem ser tratados com cuidado
- Não compartilhar com pessoas não autorizadas
- Manter em local seguro

**Recomendações:**
1. Usar VPN ao baixar em rede pública
2. Armazenar em pasta encriptada
3. Não compartilhar por email sem proteção
4. Deletar arquivos antigos periodicamente
5. Usar apenas o necessário

---

## 🛠️ Troubleshooting

### Problema: Arquivo não baixa

**Solução:**
1. Verifique pasta "Downloads"
2. Verifique configurações do navegador (popup blocker)
3. Tente outro navegador
4. Tente formato diferente (CSV → Excel)

### Problema: Arquivo está vazio

**Solução:**
1. Verifique se existem matrizes cadastradas
2. Acesse `/procedures/matrizes/` para visualizar
3. Se não houver dados, nada será exportado

### Problema: Erro ao abrir CSV

**Solução para Excel:**
1. Abra Excel
2. File → Open
3. Selecione o arquivo .csv
4. Em "Text Import Wizard", configure:
   - Encoding: UTF-8
   - Delimiter: Pipe (|)
   - Clique "Finish"

### Problema: Erro ao abrir Excel

**Solução:**
1. Verifique se Excel/LibreOffice está instalado
2. Tente duplo-clique no arquivo
3. Se não funcionar, tente outro programa:
   - LibreOffice Calc (grátis)
   - Google Sheets (online)
   - OnlyOffice (grátis)

---

## 📈 Performance

**Tempo de Exportação:**

| Quantidade | Tempo | Tamanho (CSV) | Tamanho (Excel) |
|-----------|-------|---------------|-----------------|
| 10 matrizes | < 1s | 5 KB | 10 KB |
| 100 matrizes | 1-2s | 50 KB | 100 KB |
| 1000 matrizes | 5-10s | 500 KB | 1 MB |
| 10000 matrizes | 30-60s | 5 MB | 10 MB |

**Otimização:**
- Exportação é rápida mesmo com muitos dados
- Não bloqueia a interface
- Pode fazer exportações frequentes

---

## 🔄 Comparação: CSV vs Excel

| Aspecto | CSV | Excel |
|--------|-----|-------|
| Formato | Texto | Binário |
| Tamanho | Menor | Maior |
| Compatibilidade | Universal | Excel/Sheets |
| Formatação | Nenhuma | Completa |
| Segurança | Básica | Alta (pode criptografar) |
| Análise | Python/R | Excel/VBA |
| Prototipagem | Melhor | Melhor |
| Produção | Tanto faz | Melhor |

---

## 📚 Próximos Passos

### Após Exportar:

1. **Análise de Dados**
   - Abrir em Excel
   - Criar pivô/gráficos
   - Identificar padrões

2. **Backup**
   - Armazenar em pasta segura
   - Manter com data
   - Documentar mudanças

3. **Compartilhamento**
   - Enviar para stakeholders
   - Apresentar em reunião
   - Arquivar para auditoria

4. **Integração**
   - Processar em Python
   - Importar em outro sistema
   - Sincronizar dados

---

## 🎓 Exemplos de Uso

### Exemplo 1: Contar Colaboradores por Matriz

**Excel:**
1. Abrir arquivo exportado
2. Inserir → Pivot Table
3. Rows: Matriz Nome
4. Values: Colaborador Matrícula (Count)

**Python:**
```python
import pandas as pd
df = pd.read_csv('exportacao_matrizes.csv', sep='|')
print(df.groupby('Matriz Nome')['Colaborador Matrícula'].nunique())
```

### Exemplo 2: Listar Disciplinas por Matriz

**Excel:**
1. Filter → Matriz Código
2. Selecionar matriz desejada
3. Copiar coluna Disciplina Nome

**Python:**
```python
df = pd.read_csv('exportacao_matrizes.csv', sep='|')
matriz = df[df['Matriz Código'] == 'MAT001']
disciplinas = matriz['Disciplina Nome'].unique()
print(disciplinas)
```

### Exemplo 3: Validar Dados

**Python:**
```python
df = pd.read_csv('exportacao_matrizes.csv', sep='|')

# Verificar linhas com email vazio
sem_email = df[df['Colaborador Email'].isna()]
print(f"Registros sem email: {len(sem_email)}")

# Verificar duplicatas
duplicadas = df.duplicated(subset=['Matriz Código', 'Disciplina Código', 'Colaborador Matrícula'])
print(f"Registros duplicados: {duplicada.sum()}")
```

---

## 💡 Dicas e Truques

1. **Exportar Regularmente**
   - Criar rotina semanal/mensal
   - Manter histórico de mudanças
   - Facilita auditoria

2. **Usar Timestamps**
   - Arquivo já inclui timestamp
   - Renomear apenas se necessário
   - Manter original para rastreabilidade

3. **Validar Dados**
   - Sempre verificar após exportar
   - Procurar por linhas vazias
   - Comparar com importação anterior

4. **Segurança**
   - Usar pastas específicas
   - Criptografar se necessário
   - Deletar arquivos sensíveis

5. **Performance**
   - CSV é mais rápido que Excel
   - Use CSV para análise em Python
   - Use Excel para compartilhamento

---

## 📞 Suporte

Problema ou dúvida?

1. Consulte [TROUBLESHOOTING](./TROUBLESHOOTING_EXPORTACAO_MATRIZES.md)
2. Verifique logs em DevTools (F12)
3. Contacte o suporte técnico

---

## 📌 Resumo Rápido

| Ação | Local | Resultado |
|------|-------|-----------|
| Acessar tela | `/procedures/matrizes/` | Lista de matrizes |
| Exportar CSV | Botão Exportar → CSV | Download arquivo .csv |
| Exportar Excel | Botão Exportar → Excel | Download arquivo .xlsx |
| Abrir CSV | Excel/Editor texto | Visualizar dados |
| Abrir Excel | Excel/Sheets | Visualizar formatado |
| Analisar dados | Python Pandas | Insights dos dados |

---

**Data:** 12 de Janeiro de 2026  
**Versão:** 1.0  
**Status:** ✅ Guia Completo de Exportação
