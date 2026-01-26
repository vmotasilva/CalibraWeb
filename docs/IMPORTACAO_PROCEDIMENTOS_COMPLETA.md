# 📤 Dinâmica de Importação em Massa de Procedimentos

## 📋 Visão Geral

Sistema robusto de importação de procedimentos que permite carregar centenas de registros de uma única vez através de arquivo Excel ou CSV, com validação completa de dados, tratamento de erros e relatório detalhado.

---

## 🏗️ Arquitetura

```
User Interface (Template)
    ↓
  View (importar_procedimentos_view)
    ↓
Service Layer (ImportacaoProcedimentosService)
    ├─ Carregar arquivo
    ├─ Normalizar colunas
    ├─ Validar dados
    ├─ Processar procedimentos
    └─ Gerar relatório
    ↓
Django ORM (Procedimento Model)
    ↓
PostgreSQL Database
```

---

## 📦 Componentes

### 1. **View: `importar_procedimentos_view`**
**Local:** `procedures/views/views.py`

```python
@login_required
def importar_procedimentos_view(request):
    """Importação em massa de procedimentos via arquivo Excel/CSV."""
```

**Responsabilidades:**
- Autenticação e autorização
- Recebimento do arquivo
- Instanciação do serviço
- Processamento e relatório
- Feedback ao usuário

**Fluxo:**
1. GET: Renderiza formulário vazio
2. POST: Processa arquivo
3. Retorna relatório de sucesso/erro

---

### 2. **Serviço: `ImportacaoProcedimentosService`**
**Local:** `procedures/services/importacao_procedimentos.py`

**Classe principal que orquestra o processo:**

#### **Métodos Principais:**

##### `__init__(arquivo)`
Inicializa com arquivo em memória.

```python
servico = ImportacaoProcedimentosService(request.FILES['arquivo_excel'])
```

##### `carregar_arquivo()` → bool
- Detecta formato (.xlsx, .xls, .csv)
- Carrega usando pandas
- Substitui NaN por strings vazias
- Retorna sucesso/falha

**Suporta:**
- Excel 2007+ (.xlsx)
- Excel 97-2003 (.xls)
- Valores separados por vírgula (.csv)

##### `normalizar_colunas()` → bool
- Mapeia nomes de colunas flexíveis
- Valida colunas obrigatórias
- Normaliza para nomes padrão do modelo

**Mapeamento Inteligente:**
```python
# Aceita múltiplas variações
'codigo' → ['codigo', 'Código', 'Code', 'CODIGO']
'nome' → ['nome', 'Nome', 'Title', 'Título', 'NOME']
'ultima_revisao' → ['ultima_revisao', 'última_revisão', 'Última Revisão', ...]
```

##### `_parsear_data(valor)` → date or None
- Suporta múltiplos formatos de data:
  - `DD/MM/YYYY` - Padrão português
  - `DD/MM/YY` - Dois dígitos
  - `YYYY-MM-DD` - ISO 8601
  - `DD-MM-YYYY` - Alternativo
  - `YYYY/MM/DD` - Alternativo
- Retorna None se inválido (sem erro)

**Exemplos:**
```
Input: '25/12/2024' → Output: date(2024, 12, 25)
Input: '2024-12-25' → Output: date(2024, 12, 25)
Input: '25-12-2024' → Output: date(2024, 12, 25)
Input: 'invalido' → Output: None (com warning no log)
```

##### `_validar_linha(num_linha, dados)` → (bool, list)
Valida cada linha conforme regras:

**Regras de Validação:**

| Campo | Regra |
|-------|-------|
| **codigo** | Obrigatório, 3-50 caracteres, único |
| **nome** | Obrigatório, máx 200 caracteres |
| **descricao** | Opcional, qualquer comprimento |
| **datas** | Formato flexível (vide _parsear_data) |

**Retorna Tupla:**
- `bool`: True se válido
- `list`: Erros encontrados (vazio se válido)

##### `_preparar_dados_linha(dados)` → dict
- Limpa e normaliza dados
- Parseia datas
- Remove campos vazios
- Retorna dict pronto para Django ORM

##### `processar(modo='upsert')` → dict
**Core da importação. Modos disponíveis:**

###### **Modo: `upsert` (Padrão)**
```python
# Comportamento:
- Se NOVO: Cria com dados do arquivo
- Se EXISTENTE: Atualiza campos do arquivo
- Detalhe: Atualiza APENAS campos que mudaram
```

**Exemplo:**
```
Arquivo:    codigo=POP.001, nome=Novo Nome, revisao=02
Banco (antes):     codigo=POP.001, nome=Antigo Nome, revisao=01
Banco (depois):    codigo=POP.001, nome=Novo Nome, revisao=02  ← Atualizado
```

###### **Modo: `create`**
```python
# Comportamento:
- Se NOVO: Cria
- Se EXISTENTE: Pula (sem erro, apenas log)
```

###### **Modo: `dry_run` (Teste Seguro)**
```python
# Comportamento:
- Carrega e valida arquivo
- SEM SALVAR no banco de dados
- Mostra exatamente o que SERIA feito
- Perfeito para testar antes de aplicar
```

###### **Transação Atômica**
```python
@transaction.atomic
def processar(self, modo='upsert'):
    # Se erro durante processamento:
    # → Rollback automático
    # → Banco volta ao estado original
    # → Segurança garantida
```

##### `gerar_relatorio_html()` → str
Gera relatório visual em HTML com:
- Resumo (total, criados, atualizados, erros)
- Tabela de linhas processadas com sucesso
- Tabela de erros com detalhes

**Exemplo de Saída:**
```
┌─────────────────────────────────┐
│ Total Linhas: 150               │
│ ✅ Criados: 120                 │
│ 🔄 Atualizados: 25              │
│ ❌ Erros: 5                     │
└─────────────────────────────────┘

✅ Sucesso:
┌──────┬──────────┬─────────────────────┬──────────┐
│ Linha│ Código   │ Nome                │ Status   │
├──────┼──────────┼─────────────────────┼──────────┤
│  2   │ POP.001  │ Proc Operacional 1  │ CRIADO   │
│  3   │ POP.002  │ Proc Operacional 2  │ CRIADO   │
│  4   │ POP.001  │ Proc Operacional 1A │ ATUALIZADO
```

---

### 3. **Formulário: `ImportacaoProcedimentosForm`**
**Local:** `procedures/forms/forms.py`

```python
class ImportacaoProcedimentosForm(forms.Form):
    arquivo_excel = forms.FileField(
        label="Planilha de Procedimentos",
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".xlsx, .xls, .csv"
        }),
    )
```

---

### 4. **Template: `procedimentos_importar.html`**
**Local:** `procedures/templates/procedures/procedimentos_importar.html`

**Seções:**
1. **Instruções** - Como usar o sistema
2. **Upload** - Formulário com arquivo e modo
3. **Referência** - Tabela de colunas esperadas
4. **Dicas** - Boas práticas
5. **Relatório** - Resultado após importação

---

## 🔄 Fluxo Completo

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USUÁRIO ACESSA PÁGINA                                        │
│    GET /procedures/procedimentos/importar/                      │
│    → Renderiza template com formulário                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. USUÁRIO SELECIONA ARQUIVO E CLICA PROCESSAR                 │
│    POST /procedures/procedimentos/importar/                     │
│    → arquivo_excel: file (ex: procedimentos.xlsx)              │
│    → modo: 'upsert', 'create' ou 'dry_run'                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. VIEW RECEBE REQUEST                                          │
│    importar_procedimentos_view(request)                         │
│    ✓ Verifica permissão (can_manage_procedimentos)             │
│    ✓ Valida formulário                                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. INSTANCIA SERVIÇO                                            │
│    servico = ImportacaoProcedimentosService(arquivo)            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. CARREGA ARQUIVO                                              │
│    servico.carregar_arquivo()                                   │
│    → pd.read_excel() ou pd.read_csv()                           │
│    ✓ Detecta formato                                            │
│    ✓ Carrega em DataFrame                                       │
│    ✓ Remove valores NaN                                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. NORMALIZA COLUNAS                                            │
│    servico.normalizar_colunas()                                 │
│    → Mapeia nomes flexíveis para padrão                         │
│    ✓ 'Código' → 'codigo'                                        │
│    ✓ 'NOME' → 'nome'                                            │
│    ✓ Valida obrigatórias presentes                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. PROCESSA ARQUIVO (com transação)                             │
│    servico.processar(modo)                                      │
│    Para CADA LINHA:                                             │
│      a) Valida dados                                            │
│      b) Se inválido → Registra erro                             │
│      c) Se válido → Prepara dados                               │
│      d) Aplicar lógica de modo (upsert/create/dry_run)          │
│      e) Salva no banco ou simula                                │
│      f) Registra status (CRIADO/ATUALIZADO/PULA)                │
│    → Em caso de erro: ROLLBACK automático                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 8. GERA RELATÓRIO                                               │
│    servico.gerar_relatorio_html()                               │
│    → HTML com resumo e tabelas                                  │
│    → Exibe em template                                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 9. RETORNA RESPOSTA                                             │
│    render(request, template, contexto)                          │
│    ✓ Exibe relatório com cores/ícones                          │
│    ✓ Mensagem de sucesso/aviso/erro                             │
│    ✓ Opção de voltar ou nova importação                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Estrutura de Dados

### **Modelo Procedimento**
```python
class Procedimento(models.Model):
    codigo                  CharField    Unique, 3-50 chars (obrigatório)
    nome                    CharField    Max 200 chars (obrigatório)
    descricao              TextField     Sem limite
    pasta                  CharField     Ex: QUALIDADE
    classificacao          CharField     Ex: POP, IT, INS
    autor                  CharField     Nome texto livre
    numero_revisao         CharField     Ex: 01, 02
    ultima_revisao         DateField     Última alteração
    data_aprovacao         DateField     Data aprovação
    proxima_revisao        DateField     Próxima revisão agendada
    data_validade          DateField     Validade do procedimento
    documentos_controlados CharField     Sim/Não
    matriz                 CharField     Ex: Matriz Principal
    sub_area               CharField     Ex: Área de Processos
```

### **Resultado de Processamento**
```python
resultados = {
    'total': 150,                          # Linhas no arquivo
    'criados': 120,                        # Novos procedimentos
    'atualizados': 25,                     # Procedimentos modificados
    'erros': 5,                            # Linhas com problemas
    'linhas_processadas': [                # Sucessos
        {
            'linha': 2,
            'codigo': 'POP.001',
            'nome': 'Procedimento 1',
            'status': 'CRIADO'
        }
    ],
    'erros_detalhados': [                  # Falhas
        {
            'linha': 15,
            'codigo': 'POP.005',
            'erro': 'Código duplicado na mesma importação'
        }
    ]
}
```

---

## 🛡️ Tratamento de Erros

### **Validações Implementadas**

| Erro | Causa | Ação |
|------|-------|------|
| Arquivo não suportado | .zip, .pdf, etc | Rejeita com mensagem |
| Arquivo vazio | Nenhuma linha | Rejeita |
| Coluna obrigatória faltando | Sem 'codigo' ou 'nome' | Rejeita toda importação |
| Código vazio | Campo deixado em branco | Rejeita linha |
| Código muito curto | Menos de 3 caracteres | Rejeita linha |
| Código muito longo | Mais de 50 caracteres | Rejeita linha |
| Nome vazio | Campo deixado em branco | Rejeita linha |
| Nome muito longo | Mais de 200 caracteres | Rejeita linha |
| Data inválida | 'abc' ou '32/13/2024' | Rejeita linha |
| Duplicata na mesma importação | Dois 'POP.001' | Rejeita 2ª ocorrência |

### **Tratamento de Transação**
```python
@transaction.atomic
def processar(self, modo='upsert'):
    # Se qualquer erro NÃO-TRATADO ocorrer:
    # → Transação reverte
    # → Nenhuma mudança é persistida
    # → Banco fica intacto
```

---

## 🔐 Segurança

### **Autenticação**
```python
@login_required  # Apenas usuários autenticados
```

### **Autorização**
```python
if not can_manage_procedimentos(request.user):
    # Verifica permissão específica
    # Rejeita acesso não autorizado
```

### **Validação de Dados**
- Todos os campos validados antes de salvar
- Nenhum bypass possível
- Banco de dados fica íntegro

### **Logs**
```python
logger.info(f"Importação de procedimentos realizada por {user}")
logger.error(f"Erro ao importar: {erro}")
logger.warning(f"Não foi possível parsear data: {valor}")
```

---

## 📝 Exemplos de Uso

### **Exemplo 1: Importação com Upsert (Padrão)**
```python
# Arquivo contém:
# codigo | nome | numero_revisao
# POP.001| Proc A | 01
# POP.002| Proc B | 01

# Banco contém:
# POP.001 (rev 00)

# Resultado:
# POP.001 ATUALIZADO (rev 00 → 01)
# POP.002 CRIADO (novo)
```

### **Exemplo 2: Modo Create**
```python
# Mesmo arquivo e banco anterior

# Resultado:
# POP.001 PULADO (já existe)
# POP.002 CRIADO (novo)
```

### **Exemplo 3: Modo Dry-Run (Teste)**
```python
# Sim modo anterior, mas:

# Resultado:
# POP.001 SERIA ATUALIZADO (DRY-RUN)
# POP.002 SERIA CRIADO (DRY-RUN)
# [Nada é salvo no banco]
```

---

## 📱 Template Excel Esperado

```
No | Código | Nome            | Classificação | Número Revisão | Última Revisão
1  | POP.001| Proc Operacional| POP           | 01             | 01/10/2024
2  | POP.002| Proc Segurança  | POP           | 02             | 15/11/2024
3  | IT.001 | Instrução Trab. | IT            | 01             | 20/09/2024
```

---

## 🚀 URLs e Navegação

| URL | Método | Nome | Descrição |
|-----|--------|------|-----------|
| `/procedures/procedimentos/importar/` | GET | `importar_procedimentos` | Formulário de importação |
| `/procedures/procedimentos/importar/` | POST | `importar_procedimentos` | Processar arquivo |
| `/procedures/procedimentos/` | GET | `procedimentos_list` | Botão "Importar em Massa" |

---

## 💡 Boas Práticas

### **Para Usuários**

1. **Use Dry-Run Primeiro**
   - Testa sem risco
   - Identifica problemas
   - Depois importa de verdade

2. **Prepare Dados com Cuidado**
   - Códigos únicos
   - Datas consistentes
   - Sem duplicatas

3. **Teste Pequeno Volume Primeiro**
   - 10-20 linhas
   - Verifica resultado
   - Depois faz grande volume

4. **Faça Backup do Banco**
   - Antes de importação grande
   - Protege contra erros

### **Para Desenvolvedores**

1. **Estenda com Novos Campos**
   ```python
   # Em MAPEAMENTO_COLUNAS:
   'novo_campo': ['novo_campo', 'Novo Campo', 'NOVO_CAMPO']
   
   # Em _preparar_dados_linha:
   if 'novo_campo' in dados:
       dados_preparados['novo_campo'] = valor
   ```

2. **Customizar Validação**
   ```python
   # Em _validar_linha:
   if campo == 'seu_campo':
       # Sua lógica aqui
   ```

3. **Adicionar Modo de Importação**
   ```python
   # Em processar:
   elif modo == 'seu_novo_modo':
       # Sua lógica aqui
   ```

---

## 📈 Métricas e Monitoramento

### **Informações Registradas**

```
✓ Usuário que fez importação
✓ Arquivo processado
✓ Modo utilizado
✓ Resultados (criados, atualizados, erros)
✓ Tempo de processamento
✓ Detalhes de cada erro
```

### **Acessar Logs**
```bash
# Logs do Django
tail -f logs/django.log

# Filtrar por importação
grep "importação" logs/django.log
```

---

## 🔍 Troubleshooting

### **Problema: Arquivo não reconhecido**
**Solução:** Verifique extensão (.xlsx, .xls, .csv)

### **Problema: Coluna não encontrada**
**Solução:** Use nomes conforme template ou mapeamento flexível

### **Problema: Datas inválidas**
**Solução:** Use DD/MM/YYYY ou YYYY-MM-DD

### **Problema: Códigos duplicados**
**Solução:** Use Dry-Run para identificar, corrija arquivo, reimporte

### **Problema: Erro ao salvar (rollback)**
**Solução:** Verifica relatório detalhado, corrige, tenta novamente

---

## 📞 Suporte

**Dúvidas ou Bugs?**
- Verifique logs: `/admin/logs/`
- Teste com Dry-Run primeiro
- Consulte documentação de campos
- Contate administrador

---

**Versão:** 1.0  
**Data:** Dezembro 22, 2024  
**Autor:** Sistema CalibraWeb  
**Status:** ✅ Produção
