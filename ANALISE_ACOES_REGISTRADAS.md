# 📋 ANÁLISE DE ESTRUTURA DE CAMPOS - AÇÕES REGISTRADAS
## Alinhamento de Todos os Modelos

**Data**: 11/02/2026  
**Objetivo**: Unificar a visualização de todas as ações em um único dashboard

---

## ✅ CAMPOS OBRIGATÓRIOS
```
1. Código Solução          (FK à tabela Solucao)
2. Nº Ação
3. Input/Origem            (string livre)
4. Problema
5. Lab
6. KPI
7. Descrição
8. Classificação
9. Status
10. Prioridade             (Y/N)
11. Responsável(s)         (MÚLTIPLOS - M2M)
12. Data - 1º Deadline
13. Data - 2º Deadline
14. Comentários
15. Eficácia               (Eficaz/Não Eficaz)
```

---

## 📊 ANÁLISE POR MODELO

### 1. **PlanoAcao** ✅ COMPLETO
```
✅ Código Solução      → solucao (FK)             ✅
✅ Nº Ação             → numero_acao              ✅
✅ Input               → input_origem             ✅
✅ Problema            → problema                 ✅
✅ Lab                 → laboratorio              ✅
✅ KPI                 → kpi                      ✅
✅ Descrição           → descricao                ✅
✅ Classificação       → classificacao            ✅
✅ Status              → status                   ✅
✅ Prioridade          → prioridade               ✅
❌ Responsável(s)      → responsavel_acao (ÚNICO) ⚠️ PRECISA M2M
✅ 1º Deadline         → data_primeira_deadline   ✅
✅ 2º Deadline         → data_deadline            ✅
✅ Comentários         → comentarios              ✅
✅ Eficácia            → acao_eficaz              ✅

STATUS: 14/15 ✅ (só falta M2M de responsáveis)
```

---

### 2. **SolucaoA3** ⚠️ INCOMPLETO
```
✅ Código Solução      → solucao (FK)             ✅
❌ Nº Ação             → a3_numero (mas sem numero_acao)
❌ Input               → NÃO POSSUI
✅ Problema            → problema                 ✅
✅ Lab                 → laboratorio              ✅
❌ KPI                 → NÃO POSSUI
❌ Descrição           → NÃO POSSUI (tem objetivo mas não é a mesma coisa)
❌ Classificação       → NÃO POSSUI
❌ Status              → NÃO POSSUI (tem status em Solucao pai)
❌ Prioridade          → NÃO POSSUI
❌ Responsável(s)      → lider_projeto (ÚNICO)
❌ 1º Deadline         → NÃO POSSUI
❌ 2º Deadline         → NÃO POSSUI
❌ Comentários         → NÃO POSSUI
❌ Eficácia            → NÃO POSSUI

STATUS: 4/15 ❌ (PRECISA ADICIONAR 11 CAMPOS)
```

---

### 3. **Solucao8D** ⚠️ INCOMPLETO
```
✅ Código Solução      → solucao (FK)             ✅
❌ Nº Ação             → numero_formulario (mas sem numero_acao)
❌ Input               → NÃO POSSUI
✅ Problema            → problema_identificado    ✅
✅ Lab                 → departamento (+/-)       ~
❌ KPI                 → NÃO POSSUI
✅ Descrição           → d2_descricao (parcial)   ~
❌ Classificação       → NÃO POSSUI
❌ Status              → NÃO POSSUI (tem d6_status, mas não generalizado)
❌ Prioridade          → NÃO POSSUI
❌ Responsável(s)      → lider_8d, d3_responsavel, d6_responsavel (MÚLTIPLOS mas dispersos)
❌ 1º Deadline         → d3_deadline, d6_deadline (mas não padronizado)
❌ 2º Deadline         → NÃO POSSUI
❌ Comentários         → NÃO POSSUI
❌ Eficácia            → d7_efetivo (parcial)     ~

STATUS: 3/15 ❌ (PRECISA ADICIONAR/UNIFICAR 12 CAMPOS)
```

---

### 4. **SolucaoRNC** ⚠️ INCOMPLETO
```
✅ Código Solução      → solucao (FK)             ✅
❌ Nº Ação             → numero_rnc (mas sem numero_acao)
❌ Input               → origem (predefinido, não livre)
✅ Problema            → descricao_nc              ✅
❌ Lab                 → unidade (+/-)             ~
❌ KPI                 → NÃO POSSUI
❌ Descrição           → NÃO POSSUI (tem descricao_nc mas não é descrição geral)
✅ Classificação       → classificacao             ✅
❌ Status              → NÃO POSSUI (processo RNC tem status específico)
❌ Prioridade          → NÃO POSSUI (tem frequência + risco)
❌ Responsável(s)      → responsavel (ÚNICO)       
❌ 1º Deadline         → NÃO POSSUI
❌ 2º Deadline         → NÃO POSSUI
❌ Comentários         → NÃO POSSUI
✅ Eficácia            → eficacia                  ✅

STATUS: 4/15 ❌ (PRECISA ADICIONAR 11 CAMPOS)
```

---

### 5. **SolucaoGestaoDeMudanca** ⚠️ INCOMPLETO
```
✅ Código Solução      → solucao (FK)             ✅
❌ Nº Ação             → numero_registro (sem numero_acao)
❌ Input               → NÃO POSSUI (tem tipo_mudanca predefinido)
✅ Problema            → situacao_antes            ✅
❌ Lab                 → unidade                   ~
❌ KPI                 → NÃO POSSUI
❌ Descrição           → justificativa (+/-)       ~
❌ Classificação       → tipo_mudanca (+/-)        ~
✅ Status              → STATUS_CHOICES (proposta, análise, etc) ✅
✅ Prioridade          → prioridade_mudanca        ✅
❌ Responsável(s)      → solicitante (STRING, não colaborador)
❌ 1º Deadline         → NÃO POSSUI
❌ 2º Deadline         → data_mudanca (+/-)        ~
❌ Comentários         → NÃO POSSUI
❌ Eficácia            → NÃO POSSUI

STATUS: 4/15 ❌ (PRECISA ADICIONAR/UNIFICAR 11 CAMPOS)
```

---

### 6. **RevisaoGerencial** ⚠️ INCOMPLETO
```
✅ Código Solução      → solucao (FK)             ✅
❌ Nº Ação             → numero_rg (sem numero_acao)
❌ Input               → NÃO POSSUI
❌ Problema            → NÃO POSSUI (é análise crítica, não é um "problema")
❌ Lab                 → laboratorio              ~
❌ KPI                 → NÃO POSSUI
❌ Descrição           → analises_criticas (+/-)  ~
❌ Classificação       → NÃO POSSUI
✅ Status              → STATUS_CHOICES            ✅
❌ Prioridade          → NÃO POSSUI
❌ Responsável(s)      → representante_direcao (STRING, não colaborador)
❌ 1º Deadline         → data_realizacao (+/-)    ~
❌ 2º Deadline         → NÃO POSSUI
❌ Comentários         → NÃO POSSUI
❌ Eficácia            → NÃO POSSUI

STATUS: 2/15 ❌ (PRECISA ADICIONAR 13 CAMPOS)
```

---

## 📊 RESUMO CONSOLIDADO

| Modelo | Completo | Status | Prioridade |
|--------|----------|--------|-----------|
| **PlanoAcao** | 14/15 | ✅ QUASE | 🔴 ALTA - só falta M2M |
| **SolucaoA3** | 4/15 | ⚠️ INCOMPLETO | 🟡 MÉDIA |
| **Solucao8D** | 3/15 | ⚠️ INCOMPLETO | 🟡 MÉDIA |
| **SolucaoRNC** | 4/15 | ⚠️ INCOMPLETO | 🟡 MÉDIA |
| **SolucaoGestaoDeMudanca** | 4/15 | ⚠️ INCOMPLETO | 🟡 MÉDIA |
| **RevisaoGerencial** | 2/15 | ❌ MUITO INCOMPLETO | 🟢 BAIXA |

**Total Média**: 6.17/15 (41%)

---

## 🎯 PLANO DE IMPLEMENTAÇÃO

### FASE 1: PlanoAcao (IMEDIATO)
```
1. Criar modelo M2M: Responsaveis (PlanoAcao → Colaborador)
2. Migração para adicionar tabela M2M
3. Atualizar PlanoAcaoForm com MultiSelectField
4. Atualizar view/template para mostrar multiple responsáveis

Tempo: 2-3 horas
Risco: ⚠️ BAIXO (apenas add M2M)
```

### FASE 2: Adicionar Campos Comuns a Todos
```
Para cada modelo (A3, 8D, RNC, GM, RG):
1. Adicionar campos faltantes:
   - numero_acao (IntegerField)
   - input_origem (CharField com max_length=100)
   - classificacao (CharField se não tiver aligned)
   - status (CharField se não tiver standardized)
   - prioridade (BooleanField se não tiver)
   - responsaveis_multiplos (M2M)
   - data_primeira_deadline (DateField)
   - comentarios (TextField)
   - acao_eficaz (CharField choices)

2. Criar migrações
3. Atualizar Forms
4. Atualizar Templates

Tempo: 4-6 horas
Risco: ⚠️ MÉDIO (mudanças em BD)
```

### FASE 3: View Agregada "Ações Registradas"
```
1. Criar view que faz UNION/agrega de:
   - PlanoAcao.objects.all()
   - SolucaoA3.objects.all() (via related)
   - Solucao8D.objects.all() (via related)
   - SolucaoRNC.objects.all() (via related)
   - SolucaoGestaoDeMudanca.objects.all() (via related)
   - RevisaoGerencial.objects.all() (via related)

2. Serializar com campos padrão (14 campos)

3. Template com filtros:
   - Por tipo de solução
   - Por status
   - Por responsável
   - Por prioridade
   - Busca por texto

Tempo: 3-4 horas
Risco: 🟢 BAIXO (queries de leitura)
```

---

## 📝 RECOMENDAÇÃO

**Implementar em ordem**:
1. ✅ M2M para PlanoAcao (hoje)
2. ☐ Adicionar campos faltantes (próximos 2 dias)  
3. ☐ View agregada (depois)

**Decisão**: Qual sequência você prefere?

- A. Fazer tudo agora?
- B. Começar apenas com PlanoAcao?
- C. Priorizar algum modelo específico?

---

---

## 🎯 ESTRATÉGIA DE ALINHAR

### OPÇÃO A: Abstract Base Model (Recomendado)
Criar um modelo abstrato `AcaoBase` com todos os 15 campos.
Cada solução herda de `AcaoBase`.

**Vantagens**:
- Unificado
- Fácil de agregar (Ações Registradas)
- Evita duplicação

**Desvantagens**:
- Requer migração
- Muda estrutura de tabelas

---

### OPÇÃO B: Mixin com InterfaceView
Manter modelos como estão.
Criar um `AcaoRegistradaManager` que faz UNION de todas as ações.
View agregada faz query em cada modelo.

**Vantagens**:
- Sem mudança de BD
- Rápido de implementar

**Desvantagens**:
- Menos elegante
- Falta de campos em alguns modelos

---

## ✅ RECOMENDAÇÃO FINAL

1. **Curto Prazo**: Opção B
   - Add campos faltantes a cada modelo (sem herança)
   - Cte view "Ações Registradas" que agrega

2. **Médio Prazo**: Refatorar para Opção A
   - Quando sistema estabilizar
   - Migrações bem testadas

---

## 📝 PRÓXIMAS AÇÕES

1. [ ] Verificar completamente os 3 modelos faltantes (RNC, Mudança, RG)
2. [ ] Adicionar M2M de Responsáveis a PlanoAcao
3. [ ] Adicionar campos faltantes a cada modelo
4. [ ] Criar view agregada "Ações Registradas"
5. [ ] Atualizar forms com novos campos
6. [ ] Criar migrações

---

**Status**: ANÁLISE EM PROGRESSO  
**Próximo**: Verificar 3 modelos faltantes
