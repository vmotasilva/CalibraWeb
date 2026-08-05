# 🚀 GUIA RÁPIDO - Gestão de Procedimentos em Disciplina

## O Que Foi Implementado? ✅

Uma lista **1:N** na página de detalhe da disciplina que permite:
1. **Ver** todos os procedimentos associados
2. **Adicionar** novos procedimentos
3. **Remover** procedimentos existentes

---

## Como Acessar? 🔗

```
URL: http://localhost:8000/procedures/disciplinas/{id}/
Exemplo: http://localhost:8000/procedures/disciplinas/1/
```

---

## Funcionalidades Principais 🎯

### 1️⃣ **Visualizar Procedimentos Associados**
- Tabela com 5 colunas: Ordem, Código, Nome, Obrigatório, Ações
- Mostra todos os procedimentos vinculados à disciplina
- Atualiza automaticamente após adicionar/remover

### 2️⃣ **Adicionar Procedimento**
```
Clique em: [+ Adicionar Procedimento]
           ↓
Modal abre com formulário
           ↓
Selecione procedimento no dropdown
           ↓
Defina ordem (número)
           ↓
Marque se é obrigatório (checkbox)
           ↓
Clique [Adicionar]
           ↓
✅ Procedimento adicionado!
```

### 3️⃣ **Remover Procedimento**
```
Clique em: [Remover] na linha do procedimento
           ↓
Confirmação: "Tem certeza que deseja remover?"
           ↓
Clique [OK]
           ↓
✅ Procedimento removido!
```

---

## Campos Disponíveis 📋

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| **Código** | Identificador único | DEX.002 |
| **Nome** | Título do procedimento | ISO 9001:2015 - Sistemas de gestão... |
| **Ordem** | Sequência de execução | 1, 2, 3... |
| **Obrigatório** | ✓ Sim / Não | ✓ Sim para treinar |

---

## Exemplo de Uso 💡

**Disciplina:** DISC001 - RH - Integração

**Procedimentos que queremos associar:**
1. DEX.002 - ISO 9001:2015 (Obrigatório)
2. DEX.003 - Procedimento ABC (Opcional)
3. DEX.004 - Procedimento XYZ (Obrigatório)

**Passos:**
```
1. Abra /procedures/disciplinas/1/
2. Clique "+ Adicionar Procedimento"
3. Selecione "DEX.002 - ISO 9001:2015"
4. Ordem: 1
5. Marque "Obrigatório"
6. Clique [Adicionar] ✅
7. Repita para DEX.003 e DEX.004
```

**Resultado:**
```
Tabela atualiza mostrando:
┌────┬─────────┬──────────────────┬──────────┐
│Ord │ Código  │ Nome             │ Obrig.   │
├────┼─────────┼──────────────────┼──────────┤
│ 1  │ DEX.002 │ ISO 9001:2015... │ ✓ Sim    │
│ 2  │ DEX.003 │ Procedimento ABC │ Não      │
│ 3  │ DEX.004 │ Procedimento XYZ │ ✓ Sim    │
└────┴─────────┴──────────────────┴──────────┘
```

---

## Validações Automáticas ✓

✅ **Não permite duplicatas**
- Tenta adicionar DEX.002 novamente?
- Mensagem: "O procedimento DEX.002 já está associado"

✅ **Validação de campos obrigatórios**
- Procedimento: obrigatório (*)
- Ordem: opcional (padrão 0)
- Obrigatório: opcional (padrão checked)

✅ **Segurança**
- Confirmação antes de deletar
- Token CSRF em todos os formulários
- Validação de propriedade do recurso

---

## Estrutura de Dados 🗄️

**Tabela:** `DisciplinaProcedimento`

```python
Disciplina (1) ──→ N ← Procedimento
            ↑
       M2M através de
    DisciplinaProcedimento
    
Campos:
- disciplina_id (FK)
- procedimento_id (FK)
- ordem (número)
- obrigatorio (sim/não)

Constraint: Não permite (disciplina_id, procedimento_id) duplicados
```

---

## Arquivos Envolvidos 📂

```
procedures/
├── models.py
│   └── DisciplinaProcedimento (modelo de relacionamento)
├── views/habilidades_views.py
│   ├── detalhe_disciplina_view (exibe procedimentos)
│   ├── adicionar_procedimento_disciplina_view (adiciona)
│   └── remover_procedimento_disciplina_view (remove)
├── urls.py
│   ├── /disciplinas/<id>/ (view)
│   ├── /disciplinas/<id>/procedimento/adicionar/ (POST)
│   └── /disciplinas/<id>/procedimento/<assoc_id>/remover/ (POST)
└── templates/procedures/disciplina_detalhe.html
    └── Seção "Procedimentos Associados" com modal
```

---

## Comportamento Esperado 🎬

### ✅ Caso de Sucesso
```
1. Usuário clica "+ Adicionar Procedimento"
2. Modal abre
3. Seleciona "DEX.002"
4. Clica "Adicionar"
5. Página recarrega
6. Nova linha apareça na tabela ✅
7. Mensagem verde: "Procedimento DEX.002 adicionado com sucesso!"
```

### ⚠️ Caso de Duplicata
```
1. Tenta adicionar DEX.002 novamente
2. Sistema detecta que já existe
3. Mensagem amarela: "O procedimento DEX.002 já está associado"
4. Tabela não é alterada
```

### ❌ Caso de Erro
```
1. Procedimento não existe ou foi deletado
2. Mensagem vermelha: "Procedimento não encontrado"
3. Nenhuma alteração é feita
```

---

## Dicas Úteis 💡

1. **Ordenação:** Use o campo "Ordem" para definir a sequência de execução (1, 2, 3...)
2. **Obrigatoriedade:** Marque ✓ para procedimentos essenciais, deixe desmarcado para opcionais
3. **Pesquisa:** No dropdown, você pode digitar para filtrar procedimentos
4. **Remover:** Clique "Remover" e confirme - será tão rápido quanto adicionar

---

## Mensagens do Sistema 📢

| Tipo | Exemplos |
|------|----------|
| ✅ **Verde (Sucesso)** | "Procedimento XX adicionado com sucesso!" |
| ⚠️ **Amarelo (Aviso)** | "O procedimento XX já está associado" |
| ❌ **Vermelho (Erro)** | "Procedimento não encontrado" |

---

## Próximos Passos (Sugestões)

- [ ] Ordenar procedimentos arrastando (drag & drop)
- [ ] Importar múltiplos procedimentos em lote
- [ ] Histórico de mudanças
- [ ] Duplicar associações de outra disciplina

---

**Data de Implementação:** 29/12/2025  
**Status:** ✅ Funcional e Testado  
**Ambiente:** Django 5.0.14 + SQLite + Bootstrap 5
