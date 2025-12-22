# 📤 Guia de Uso - Importação em Massa de Procedimentos

## 🎯 Objetivo

Importar centenas de procedimentos simultaneamente através de arquivo Excel ou CSV, com validação automática, detecção de erros e relatório detalhado.

---

## 🚀 Quick Start (5 minutos)

### 1. Acesse a Interface
```
https://calibraweb.app/procedures/procedimentos/importar/
```

### 2. Baixe o Template
Clique em **"📥 Baixar Template Excel"** para obter arquivo estruturado

### 3. Preencha seus Dados
Abra no Excel e preencha com seus procedimentos:

```
| Código   | Nome                      | Classificação | Número Revisão |
|----------|---------------------------|---------------|----------------|
| POP.001  | Procedimento Operacional 1| POP           | 01             |
| POP.002  | Procedimento Operacional 2| POP           | 02             |
| IT.001   | Instrução de Trabalho     | IT            | 01             |
```

### 4. Faça Upload
- Clique em "Escolher arquivo"
- Selecione seu arquivo preenchido
- Escolha modo (recomendado: **Upsert**)
- Clique em "▶ Processar Importação"

### 5. Veja Resultado
Relatório mostra exatamente o que foi criado/atualizado/errou

---

## 📋 Colunas Esperadas

| Campo | Obrigatório | Formato | Exemplo |
|-------|---------|---------|---------|
| **codigo** | ✅ Sim | 3-50 caracteres, único | `POP.001` |
| **nome** | ✅ Sim | Até 200 caracteres | `Procedimento Operacional` |
| **descricao** | ❌ Não | Texto livre | `Objetivo e função do proc.` |
| **pasta** | ❌ Não | Ex: QUALIDADE | `QUALIDADE` |
| **classificacao** | ❌ Não | POP, IT, INS, DOC | `POP` |
| **autor** | ❌ Não | Nome do responsável | `João Silva` |
| **numero_revisao** | ❌ Não | Ex: 01, 02 | `01` |
| **ultima_revisao** | ❌ Não | DD/MM/YYYY ou YYYY-MM-DD | `25/12/2024` |
| **data_aprovacao** | ❌ Não | DD/MM/YYYY ou YYYY-MM-DD | `20/12/2024` |
| **proxima_revisao** | ❌ Não | DD/MM/YYYY ou YYYY-MM-DD | `25/12/2025` |
| **data_validade** | ❌ Não | DD/MM/YYYY ou YYYY-MM-DD | `25/12/2025` |
| **documentos_controlados** | ❌ Não | Sim/Não ou S/N | `Sim` |
| **matriz** | ❌ Não | Nome da matriz | `Matriz Principal` |
| **sub_area** | ❌ Não | Área dentro da matriz | `Área de Processos` |

---

## 🔄 Modos de Importação

### **Upsert** (Recomendado)
```
✓ Cria procedimentos NOVOS
✓ ATUALIZA procedimentos existentes
→ Modo padrão e mais seguro
```

**Quando usar:** Quando vai importar dados atualizados

**Exemplo:**
```
Arquivo tem: POP.001 (rev 02), POP.002 (novo)
Banco tem:   POP.001 (rev 01)

Resultado:   POP.001 ATUALIZADO (01→02), POP.002 CRIADO
```

---

### **Create** (Apenas Novos)
```
✓ Cria procedimentos NOVOS
✗ IGNORA procedimentos existentes (sem erro)
→ Mais conservador, não modifica existentes
```

**Quando usar:** Quando quer adicionar sem arriscar alterações

**Exemplo:**
```
Arquivo tem: POP.001, POP.002
Banco tem:   POP.001

Resultado:   POP.001 PULADO, POP.002 CRIADO
```

---

### **Dry-Run** (Teste)
```
✓ Carrega e valida arquivo
✓ SIMULA o que seria feito
✗ NÃO salva nada no banco
→ Perfeito para testar antes
```

**Quando usar:** SEMPRE antes de importação grande

**Exemplo:**
```
Arquivo: procedimentos.xlsx
Modo: Dry-Run

Resultado: "Seria criado 150 procedimentos, 25 atualizados"
(Nada foi de fato salvo)
```

---

## ✅ Validações Automáticas

Sistema valida **antes** de salvar qualquer coisa:

### Validações Obrigatórias

- ✓ **Código** deve ter 3-50 caracteres
- ✓ **Código** deve ser único no banco
- ✓ **Nome** é obrigatório (até 200 chars)
- ✓ Não há duplicatas na mesma importação
- ✓ Datas em formato válido

### O Que NÃO Valida (Permite)

- ❌ Espaços em branco extras (serão removidos)
- ❌ Campos opcionais vazios (serão ignorados)
- ❌ Descrições muito longas (sem limite)
- ❌ Nomes que já existem (para outros campos)

---

## 📊 Formatos de Data Suportados

Sistema aceita múltiplos formatos automaticamente:

```
✓ 25/12/2024    (DD/MM/YYYY)      Padrão português
✓ 25/12/24      (DD/MM/YY)        Sem século
✓ 2024-12-25    (YYYY-MM-DD)      ISO 8601
✓ 25-12-2024    (DD-MM-YYYY)      Alternativo
✓ 2024/12/25    (YYYY/MM/DD)      Alternativo

✗ 12/25/2024    (MM/DD/YYYY)      Americano (NÃO)
✗ 25122024      (sem separador)   NÃO funciona
```

---

## 🛡️ Segurança

### Autenticação
- ✓ Apenas usuários logados podem importar
- ✓ Requer permissão específica (manage_procedimentos)

### Dados
- ✓ Validação completa antes de salvar
- ✓ Transação atômica (tudo ou nada)
- ✓ Rollback automático se erro
- ✓ Log de cada importação

### Auditoria
- ✓ Registra quem importou
- ✓ Registra quando foi importado
- ✓ Registra quantos criados/atualizados/erros
- ✓ Detalhes de cada erro

---

## 🐛 Troubleshooting

### ❌ "Arquivo não suportado"
**Causa:** Formato errado (.zip, .pdf, etc)
**Solução:** Use .xlsx, .xls ou .csv

### ❌ "Coluna obrigatória faltando: codigo"
**Causa:** Coluna 'codigo' ou similar não encontrada
**Solução:** 
- Verifique nomes das colunas no template
- Use exatamente como template sugere
- Ou sistema faz mapeamento automático (Código, CODIGO, etc)

### ❌ "Código deve ter entre 3 e 50 caracteres"
**Causa:** Código muito curto (AB) ou longo (>50)
**Solução:** Código entre 3-50 caracteres

### ❌ "Nome é obrigatório"
**Causa:** Campo 'nome' vazio
**Solução:** Preencha nome para cada linha

### ❌ "Data inválida: abc"
**Causa:** Formato de data não reconhecido
**Solução:** Use DD/MM/YYYY ou YYYY-MM-DD

### ❌ "Código duplicado na mesma importação"
**Causa:** Mesmo código em 2 linhas do arquivo
**Solução:** Remova duplicata ou use modo diferente

### ⚠️ "Erro ao processar arquivo"
**Causa:** Arquivo corrompido ou erro desconhecido
**Solução:** 
1. Use Dry-Run para testar
2. Veja detalhes no log
3. Tente arquivo menor
4. Contate suporte se persistir

---

## 📝 Exemplos de Uso

### Exemplo 1: Importar Novos Procedimentos
```
Arquivo: procedimentos_novos.xlsx
Modo: UPSERT (padrão)
Resultado: 50 novos procedimentos criados
```

### Exemplo 2: Atualizar Procedimentos Existentes
```
Arquivo: procedimentos_revisados.xlsx (mesmo códigos, novos números revisão)
Modo: UPSERT
Resultado: 30 procedimentos atualizados (revisão alterada)
```

### Exemplo 3: Teste Antes de Importar
```
Arquivo: grande_lista_procedimentos.xlsx (1000 linhas)
Modo: DRY-RUN
Resultado: "Seria criado 950, atualizado 50"
→ Depois fazer com modo UPSERT
```

### Exemplo 4: Adicionar Sem Risco
```
Arquivo: novos_procedimentos.xlsx
Modo: CREATE
Resultado: Apenas novos são criados, existentes ignorados
→ Seguro mesmo se arquivo tiver duplicatas
```

---

## 📈 Relatório de Importação

### Resumo Executivo
```
Total Linhas:    150
✅ Criados:      120
🔄 Atualizados:  25
❌ Erros:        5
```

### Tabela de Sucessos
Mostra cada linha processada com sucesso:
- Número da linha
- Código do procedimento
- Nome
- Status (CRIADO/ATUALIZADO/PULA)

### Tabela de Erros
Detalha cada erro encontrado:
- Número da linha
- Código (se houver)
- Mensagem de erro específica

---

## ⚡ Performance

### Velocidade
- **Até 100 linhas:** < 5 segundos
- **Até 500 linhas:** 10-20 segundos
- **Até 1000 linhas:** 30-60 segundos
- **Acima disso:** Contacte suporte

### Otimizações
- Validação em paralelo quando possível
- Batch processing no banco
- Índices no código (chave única)

---

## 🎓 Boas Práticas

### ✅ Faça

1. **Teste com Dry-Run primeiro**
   ```
   - Sempre teste antes de importação grande
   - Identificar erros antes de salvar
   - Toma apenas 1-2 minutos
   ```

2. **Use Excel/CSV estruturado**
   ```
   - Baixe template fornecido
   - Siga formatação
   - Sem linhas em branco
   ```

3. **Valide dados antes**
   ```
   - Códigos únicos
   - Datas válidas
   - Campos preenchidos
   ```

4. **Faça backup antes**
   ```
   - Importação grande?
   - Faça backup do banco
   - Protege contra erros
   ```

### ❌ Não Faça

1. **Não misture formatos de data**
   ```
   ✗ Arquivo com: DD/MM/YYYY em uma coluna, YYYY-MM-DD em outra
   → Sistema pode não reconhecer
   ```

2. **Não use caracteres especiais em código**
   ```
   ✗ POP@001 ou POP#001
   → Use apenas: POP.001, POP-001 ou POP_001
   ```

3. **Não apague arquivo antes de verificar resultado**
   ```
   ✗ Faça import, depois delete arquivo
   → Se teve erro, não consegue verificar
   → Sempre mantenha cópia
   ```

4. **Não importe sem validação**
   ```
   ✗ Arquivos de terceiros sem revisar
   → Podem ter dados inconsistentes
   → Sempre faça Dry-Run antes
   ```

---

## 🔧 Configuração Avançada

### Alterar Permissão
Por padrão, apenas staff com permissão `manage_procedimentos` pode importar.

Para alterar em `settings.py`:
```python
IMPORTACAO_PROCEDIMENTOS_PERMITIDA_PARA = ['staff', 'quality_manager']
```

### Customizar Validações
Editar `procedures/services/importacao_procedimentos.py`:
```python
def _validar_linha(self, num_linha, dados):
    # Adicionar sua lógica aqui
```

### Adicionar Novo Campo
```python
# Em MAPEAMENTO_COLUNAS:
'novo_campo': ['novo_campo', 'Novo Campo', 'NOVO_CAMPO']

# Em _preparar_dados_linha:
if 'novo_campo' in dados:
    dados_preparados['novo_campo'] = valor
```

---

## 📞 Suporte

### Dúvidas Frequentes

**P: Posso importar imagens ou arquivos?**
R: Não, apenas dados de texto (Excel/CSV). Para arquivos, use GED.

**P: Quanto tempo leva para importar 10.000 procedimentos?**
R: ~10 minutos. Para volumes muito maiores, contate suporte.

**P: Posso agendar importações automáticas?**
R: Não atualmente, mas pode solicitar feature.

**P: O que acontece se internet cair no meio da importação?**
R: Rollback automático. Nada é salvo. Tente novamente.

### Reportar Problema
1. Faça Dry-Run e capture o erro
2. Capture screenshot do relatório
3. Envie para suporte@calibraweb.app com:
   - Arquivo que estava testando
   - Screenshot do erro
   - Quantas linhas tinham

---

## 📚 Documentação Relacionada

- [Arquitetura Técnica](/docs/IMPORTACAO_PROCEDIMENTOS_COMPLETA.md)
- [API de Importação](/docs/api/importacao.md)
- [Testes Unitários](/procedures/tests/test_importacao_procedimentos.py)
- [Script de Demonstração](/scripts/demo_importacao_procedimentos.py)

---

**Versão:** 1.0  
**Última Atualização:** Dezembro 22, 2024  
**Status:** ✅ Produção
