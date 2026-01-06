# GUIA DE USO: SISTEMA DE PLANEJAMENTO COM MÚLTIPLAS ORIGENS
## Geração Automática de Demanda a partir da Matriz de Habilidades

---

## 1. VISÃO GERAL

Este sistema permite criar planejamentos de treinamento de **3 formas diferentes**:

| Tipo | Descrição | Melhor para |
|------|-----------|------------|
| 📋 **LIVRE** | Planejamento manual tradicional | Demandas espontâneas ou customizadas |
| 📊 **MATRIZ** | Gerado automaticamente de gaps | Cobrir défices identificados na matriz |
| 📥 **DEMANDA** | De solicitações externas | Demandas de RH ou gerência |

---

## 2. FLUXO 1: CRIAR PLANEJAMENTO LIVRE

### Passo 1: Acessar formulário
```
Navegue para: /procedures/planejamentos/novo/
```

### Passo 2: Preencher formulário
```
1. Origem: Selecione "Planejamento Livre" ✓
   → Campo "Procedimento" aparece (obrigatório)
   → Campo "Disciplina" desaparece

2. Título: "Treinamento NR-12 - Grupo A"

3. Procedimento: Selecione o procedimento de treinamento

4. Colaboradores: Marque os que participarão
   (Múltipla seleção com scroll)

5. Instrutor: Quem vai ministrar (opcional)

6. Data Prevista: Data do treinamento

7. Local: Onde será realizado (opcional)

8. Status: Deixe em "Planejado"

9. Observações: Notas adicionais
```

### Passo 3: Salvar
```
Clique em "Salvar"
→ Planejamento criado com origem=LIVRE
→ Redireciona para detalhe do planejamento
```

---

## 3. FLUXO 2: GERAR AUTOMATICAMENTE DA MATRIZ

Este é o fluxo principal para **automação de demandas**.

### Passo 1: Selecionar Matriz
```
Navegue para: /procedures/planejamentos/matriz/selecionar/

Você verá uma lista de matrizes disponíveis:
┌─────────────────────────────────────────┐
│ Matriz de Habilidades RH                │
│ 7 disciplinas                           │
│ Criada em: 15/12/2025                   │
│ [Clique para gerar]                     │
└─────────────────────────────────────────┘

Clique na matriz desejada
```

### Passo 2: Selecionar Disciplina com Gap
```
Sistema exibe apenas disciplinas com "gaps":

DISCIPLINAS COM GAPS DETECTADOS:
┌────────────────────────────────────────────┐
│ DIS C001 - Integração de Dados             │
│ 5 colaboradores com avaliação < 2          │
│                                            │
│ DIS C002 - Metrologia                      │
│ 3 colaboradores com avaliação < 2          │
│                                            │
│ DIS C003 - Relatórios Técnicos             │
│ 2 colaboradores com avaliação < 2          │
└────────────────────────────────────────────┘

Selecione a disciplina que deseja trabalhar.
```

### Passo 3: Informações de Execução
```
Complete o formulário:

Disciplina: [Selecionada no passo 2]

Data Prevista: [Data do treinamento]
Exemplo: 15/01/2026

Local: [Onde será realizado]
Exemplo: "Sala de Treinamento A" ou "Online"

RESUMO:
├─ Matriz: Matriz de Habilidades RH
├─ Tipo: Matriz de Habilidades
└─ Status Inicial: Planejado
```

### Passo 4: Geração Automática
```
Sistema faz internamente:

1. Identifica todos os colaboradores com:
   ├─ Avaliação nesta disciplina < 2 (0 ou 1)
   ├─ Nota ≠ -1 (não é N/A)

2. Para CADA colaborador + CADA procedimento da disciplina:
   ├─ Verifica se já existe planejamento ativo
   ├─ Se não existe: CRIA novo planejamento com
   │  ├─ origem='MATRIZ'
   │  ├─ disciplina=selecionada
   │  ├─ procedimento=da disciplina
   │  ├─ data_prevista=informada
   │  ├─ status='PLANEJADO'
   │  └─ colaborador=identificado
   │
   └─ Observações com contexto:
      "Gerado automaticamente da Matriz de Habilidades.
       Avaliação da disciplina: Insuficiente (1)
       Colaborador: João Silva"

Resultado:
✅ 15 planejamentos criados
→ Redireciona para lista de planejamentos
```

### Passo 5: Visualizar Resultado
```
Acesse: /procedures/planejamentos/

Filtros disponíveis:
├─ Origem: "Matriz de Habilidades"
├─ Status: "Planejado"
└─ Data: Janeiro/2026

Verá todos os planejamentos gerados,
agrupados por:
- Colaborador
- Procedimento
- Disciplina
```

---

## 4. EXEMPLO PRÁTICO: CENÁRIO COMPLETO

### Situação:
```
Matriz: "Calibração de Equipamentos"

Disciplinas:
- D001: Balança Analítica (4 colaboradores, 1 com nota 1)
- D002: Micrômetro (3 colaboradores, 2 com nota 0)
- D003: Paquímetro (5 colaboradores, 3 com nota 1)

Procedimentos associados:
- D001 → P001 (Calibração Balança), P002 (Documentação)
- D002 → P003 (Micrômetro Uso), P004 (Limpeza)
- D003 → P005 (Paquímetro Básico)
```

### Execução:
```
1. Acesso: /procedures/planejamentos/matriz/selecionar/
   → Clica em "Calibração de Equipamentos"

2. Formulário de geração:
   ├─ Disciplina: "D003 - Paquímetro" (3 gaps)
   ├─ Data: 20/01/2026
   └─ Local: Laboratório de Metrologia

3. Clica "Gerar Planejamentos"

Sistema gera:
├─ Planejamento 1:
│  ├─ Título: "Paquímetro - P005"
│  ├─ Colaborador: Ana Silva (nota 1)
│  ├─ Origem: MATRIZ
│  ├─ Data: 20/01/2026
│  └─ Observações: "Avaliação: Insuficiente (1)"
│
├─ Planejamento 2:
│  ├─ Título: "Paquímetro - P005"
│  ├─ Colaborador: Carlos Santos (nota 1)
│  ├─ Origem: MATRIZ
│  ├─ Data: 20/01/2026
│  └─ Observações: "Avaliação: Insuficiente (1)"
│
└─ Planejamento 3:
   ├─ Título: "Paquímetro - P005"
   ├─ Colaborador: Marina Costa (nota 0)
   ├─ Origem: MATRIZ
   ├─ Data: 20/01/2026
   └─ Observações: "Avaliação: Não Avaliado/Crítico (0)"

Resultado: ✅ 3 planejamentos criados
```

---

## 5. FILTROS E BUSCA NA LISTA

### Acessar Lista:
```
/procedures/planejamentos/
```

### Filtros Disponíveis:
```
1. Busca por Termo:
   ├─ Busca em: Título, Procedimento (código ou nome)
   └─ Exemplo: "NR-12" ou "Integração"

2. Status:
   ├─ Planejado
   ├─ Confirmado
   ├─ Realizado
   └─ Cancelado

3. Procedimento:
   ├─ Dropdown com procedimentos ativos
   └─ Mostra primeiras 100

4. Mês:
   ├─ Formato: YYYY-MM
   ├─ Exemplo: 2026-01
   └─ Filtra por período
```

### Estatísticas Exibidas:
```
Total: 42 planejamentos
├─ Planejado: 25
├─ Confirmado: 10
├─ Realizado: 5
└─ Cancelado: 2
```

---

## 6. EDITAR PLANEJAMENTO EXISTENTE

### Acessar:
```
/procedures/planejamentos/<id>/editar/
```

### Modificações Permitidas:
```
✅ Pode modificar:
   ├─ Título
   ├─ Status
   ├─ Colaboradores (adicionar/remover)
   ├─ Instrutor
   ├─ Data Prevista/Realizada
   ├─ Local
   ├─ Carga Horária
   └─ Observações

❌ Não pode modificar:
   ├─ Origem (fixa no momento da criação)
   ├─ Procedimento (de MATRIZ gerados)
   └─ Disciplina (de MATRIZ gerados)
```

### Exemplo:
```
1. Abre planejamento gerado da MATRIZ
2. Modifica: "Data Prevista" de 20/01 para 27/01
3. Adiciona: "Sala de Treinamento B" em Local
4. Clica "Salvar"
→ Atualizado com sucesso
```

---

## 7. ALTERAR STATUS DE PLANEJAMENTO

### Fluxo Completo:
```
PLANEJADO → CONFIRMADO → REALIZADO
                     ↓
                 CANCELADO
```

### Como Alterar:
```
1. Acesse detalhe do planejamento:
   /procedures/planejamentos/<id>/

2. Clique em "Alterar Status"

3. Selecione novo status:
   ├─ PLANEJADO: Ainda em fase de planejamento
   ├─ CONFIRMADO: Confirmado com instrutores/salas
   ├─ REALIZADO: Treinamento foi executado
   └─ CANCELADO: Treinamento foi cancelado

4. Se status for REALIZADO:
   └─ Data realizada é preenchida automaticamente

5. Clique "Salvar"
```

---

## 8. CRIAR REGISTROS DE TREINAMENTO

Após executar um treinamento (status REALIZADO):

### Acessar:
```
/procedures/planejamentos/<id>/criar-registros/
```

### Funcionalidade:
```
Cria registros individuais de treinamento
para cada colaborador do planejamento.

Dados preenchidos automaticamente:
├─ Procedimento: Do planejamento
├─ Colaborador: De cada selecionado
├─ Data: Da execução
├─ Instrutor: Do planejamento
└─ Observações: Referência ao planejamento
```

### Exemplo:
```
Planejamento tem 3 colaboradores:
1. Ana Silva
2. Carlos Santos  
3. Marina Costa

Clica "Criar Registros"
→ Sistema cria 3 RegistroTreinamento
→ Todos com data e instrutor do planejamento
→ Status do planejamento = REALIZADO
```

---

## 9. ADMIN DJANGO: GERENCIAR DADOS

### Acessar Admin:
```
/admin/procedures/planejamentotreinamento/
```

### O que pode fazer no Admin:

#### a. Visualizar Todos:
```
Listagem com:
├─ Título
├─ Origem (LIVRE/MATRIZ/DEMANDA)
├─ Data Prevista
└─ Status
```

#### b. Filtrar por:
```
├─ Origem
├─ Status
└─ Data Prevista (range)
```

#### c. Buscar por:
```
├─ Título
└─ Observações
```

#### d. Editar Campos (diretamente no admin):
```
Fieldsets organizados:
┌─ Identificação
│  ├─ Título
│  └─ Origem
├─ Relacionamentos
│  ├─ Procedimento
│  └─ Disciplina
├─ Participantes
│  ├─ Colaboradores (m2m)
│  └─ Instrutor
├─ Execução
│  ├─ Data Prevista
│  ├─ Data Realizada
│  ├─ Carga Horária
│  └─ Local
└─ Status
   ├─ Status
   └─ Observações
```

---

## 10. RASTREAMENTO E AUDITORIA

### Campos de Auditoria Automáticos:
```
Cada planejamento registra:
├─ criado_em: Data/hora de criação
└─ atualizado_em: Data/hora da última edição
```

### Como Saber a Origem:
```
1. Acesse detalhe do planejamento
2. Veja campo "Origem/Tipo de Planejamento"
3. Observações contêm contexto adicional

Exemplos de Origem:
┌─ LIVRE
│  └─ "Criado manualmente por usuário"
├─ MATRIZ
│  └─ "Gerado automaticamente da Matriz de Habilidades.
│     Avaliação: Insuficiente (1)
│     Colaborador: João Silva"
└─ DEMANDA
   └─ "Solicitado por: Gerência RH"
```

---

## 11. TROUBLESHOOTING

### Problema 1: "Nenhuma disciplina com gaps disponível"
```
❌ Significado:
   Todas as disciplinas da matriz têm 100% de conformidade

✅ Solução:
   ├─ Aguarde próximas avaliações da matriz
   ├─ Verifique se matriz está ativa
   └─ Confirme se há colaboradores com nota < 2
```

### Problema 2: "Planejamento já existe para este colaborador"
```
❌ Significado:
   Há planejamento PLANEJADO ou CONFIRMADO já criado

✅ Solução:
   ├─ Edite o existente em vez de criar novo
   ├─ Cancele o anterior se não mais necessário
   └─ Ou use data diferente se for treinar novamente
```

### Problema 3: Campo "Procedimento" não aparece
```
❌ Significado:
   Origem selecionada não é "LIVRE"

✅ Solução:
   ├─ Selecione origem "Planejamento Livre"
   ├─ Refresh da página se necessário
   └─ Verifique JavaScript do browser
```

### Problema 4: Não consigo salvar o formulário
```
❌ Significado:
   Campos obrigatórios faltando

✅ Solução conforme origem:
   
   LIVRE:
   ├─ Procedimento: obrigatório
   ├─ Colaboradores: obrigatório
   └─ Data Prevista: obrigatório
   
   MATRIZ:
   ├─ Disciplina: obrigatório
   ├─ Colaboradores: obrigatório
   └─ Data Prevista: obrigatório
   
   DEMANDA:
   ├─ Colaboradores: obrigatório
   └─ Data Prevista: obrigatório
```

---

## 12. DICAS E BOAS PRÁTICAS

### ✅ Recomendado:

1. **Agendar Geração Automática**
   ```
   Após ciclo de avaliações da matriz,
   gere planejamentos automaticamente
   para cobrir todos os gaps detectados.
   ```

2. **Revisar Antes de Confirmar**
   ```
   Após geração automática:
   ├─ Valide datas e locais
   ├─ Confirme disponibilidade de instrutores
   └─ Ajuste conforme necessário
   ```

3. **Manter Histórico**
   ```
   Sistema rastreia:
   ├─ Data de criação
   ├─ Origem (qual matriz/gap)
   └─ Progressão de status
   ```

4. **Usar Filtros Eficientemente**
   ```
   Busque por:
   ├─ Origem = "MATRIZ" para ver gerados automaticamente
   ├─ Status = "PLANEJADO" para ações pendentes
   └─ Procedimento para validar cobertura
   ```

### ❌ Evitar:

1. **Criar duplicatas manualmente**
   ```
   Se matriz já gerou, não crie manual similar
   ```

2. **Deixar status como PLANEJADO indefinidamente**
   ```
   Avance para CONFIRMADO ou CANCELADO
   ```

3. **Modificar origem após criação**
   ```
   Não é permitido; delete e recrie se necessário
   ```

---

## 13. PERGUNTAS FREQUENTES (FAQ)

### P: Quantos planejamentos podem ser gerados de uma vez?
```
R: Ilimitado. Sistema cria 1 por:
   (colaborador com gap) × (procedimento da disciplina)
```

### P: Posso criar planejamento para disciplina que não tem gap?
```
R: Sim! Use "Planejamento Livre".
   Automático só funciona para disciplinas com gaps.
```

### P: O que significa avaliação "N/A" (valor -1)?
```
R: Colaborador não foi avaliado nesta disciplina.
   Sistema ignora (-1) na geração automática.
```

### P: Posso alterar disciplina após criar planejamento?
```
R: Não para planejamentos de MATRIZ.
   Sim para planejamentos de LIVRE.
   
   Se errou: Delete e crie novo.
```

### P: Planejamento gerado automaticamente pode ser editado?
```
R: Sim! Pode modificar praticamente tudo
   EXCETO: origem, procedimento, disciplina (de MATRIZ)
```

### P: Como saber qual gap gerou qual planejamento?
```
R: Leia o campo "Observações":
   "Gerado automaticamente da Matriz de Habilidades.
    Avaliação da disciplina: Insuficiente (1)
    Colaborador: João Silva"
```

---

## 14. INDICADORES E MÉTRICAS

### Como Medir Efetividade:

```
1. Cobertura de Gaps:
   = (Planejamentos MATRIZ gerados) / (Total de gaps detectados)
   Meta: 100%

2. Taxa de Execução:
   = (Planejamentos status REALIZADO) / (Total MATRIZ)
   Meta: 80%+

3. Tempo Médio de Execução:
   = (Data Realizada - Data Prevista) média
   Meta: ≤ 30 dias

4. Distribuição por Origem:
   ├─ Qual % vem de MATRIZ
   ├─ Qual % vem de LIVRE
   └─ Qual % vem de DEMANDA
```

---

**Desenvolvido para facilitar a gestão de treinamentos vinculada à Matriz de Habilidades**

