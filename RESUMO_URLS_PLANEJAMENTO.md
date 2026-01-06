# RESUMO RÁPIDO: URLS E ACESSO AO SISTEMA

## URLs Principais

### 1. **Lista de Planejamentos**
```
GET /procedures/planejamentos/
```
Visualiza todos os planejamentos com filtros por:
- Termo (título, procedimento)
- Status
- Procedimento
- Mês

---

### 2. **Criar Novo Planejamento (Manual/Livre)**
```
GET  /procedures/planejamentos/novo/
POST /procedures/planejamentos/novo/
```
Formulário para criar planejamento manualmente
- Origem: Planejamento Livre
- Procedimento obrigatório
- Colaboradores obrigatórios
- Data prevista obrigatória

---

### 3. **Gerar Planejamentos da Matriz (RECOMENDADO)**

#### 3.1 Selecionar Matriz
```
GET /procedures/planejamentos/matriz/selecionar/
```
Lista de matrizes disponíveis com contagem de disciplinas
Clique para iniciar processo de geração

#### 3.2 Gerar Planejamentos Automaticamente
```
GET  /procedures/planejamentos/matriz/<int:matriz_id>/gerar/
POST /procedures/planejamentos/matriz/<int:matriz_id>/gerar/
```
Formulário para:
- Selecionar disciplina (apenas com gaps)
- Data prevista do treinamento
- Local (opcional)

Sistema gera automaticamente:
- 1 planejamento por (colaborador com gap × procedimento)
- Com origem='MATRIZ'
- Com disciplina vinculada
- Com colaborador vinculado
- Com observações contextuais

---

### 4. **Detalhe de Planejamento**
```
GET /procedures/planejamentos/<int:planejamento_id>/
```
Visualiza informações completas do planejamento
- Todos os campos
- Colaboradores vinculados
- Registros de treinamento relacionados
- Botões para editar, alterar status, deletar

---

### 5. **Editar Planejamento**
```
GET  /procedures/planejamentos/<int:planejamento_id>/editar/
POST /procedures/planejamentos/<int:planejamento_id>/editar/
```
Permite modificar:
- Título, datas, local, instrutor
- Status
- Colaboradores (adicionar/remover)
- Observações

❌ NÃO permite modificar:
- Origem (fixa)
- Procedimento (de MATRIZ)
- Disciplina (de MATRIZ)

---

### 6. **Alterar Status**
```
GET  /procedures/planejamentos/<int:planejamento_id>/status/
POST /procedures/planejamentos/<int:planejamento_id>/status/
```
Muda status entre:
- PLANEJADO → CONFIRMADO → REALIZADO
- ou CANCELADO

---

### 7. **Criar Registros de Treinamento**
```
GET  /procedures/planejamentos/<int:planejamento_id>/criar-registros/
POST /procedures/planejamentos/<int:planejamento_id>/criar-registros/
```
Após executar treinamento:
- Cria RegistroTreinamento para cada colaborador
- Preenche data, instrutor, observações automaticamente
- Atualiza status para REALIZADO

---

### 8. **Admin Django**
```
GET /admin/procedures/planejamentotreinamento/
GET /admin/procedures/disciplinaprocedimento/
GET /admin/procedures/disciplina/
```
Gerenciar dados diretamente
- Criar, editar, deletar
- Filtrar por origem/status
- Buscar por título

---

## Fluxo Recomendado: Geração de Demandas

```
1. Executar Avaliações da Matriz
   /procedures/avaliacoes/

2. Gerar Planejamentos da Matriz
   /procedures/planejamentos/matriz/selecionar/
   → /procedures/planejamentos/matriz/<id>/gerar/

3. Revisar Planejamentos Gerados
   /procedures/planejamentos/
   [Filtro: origem=MATRIZ, status=PLANEJADO]

4. Confirmar Planejamentos
   /procedures/planejamentos/<id>/status/
   [Mudar para: CONFIRMADO]

5. Executar Treinamentos
   [Calendário realiza na data prevista]

6. Registrar Execução
   /procedures/planejamentos/<id>/criar-registros/
   [Status: REALIZADO]

7. Analisar Cobertura
   Verificar se todos os gaps foram cobertos
```

---

## Campos Condicionais no Formulário

### Quando origem = "LIVRE"
```
Campos Obrigatórios:
✓ Procedimento
✓ Colaboradores
✓ Título
✓ Data Prevista

Campos Opcionais:
- Instrutor
- Local
- Carga Horária
- Observações
```

### Quando origem = "MATRIZ"
```
Campos Obrigatórios:
✓ Disciplina
✓ Colaboradores
✓ Título
✓ Data Prevista

Campos Opcionais:
- Procedimento (auto-preenchido)
- Instrutor
- Local
- Carga Horária
```

### Quando origem = "DEMANDA"
```
Campos Obrigatórios:
✓ Colaboradores
✓ Título
✓ Data Prevista

Campos Opcionais:
- Procedimento
- Disciplina
- Instrutor
- Local
- Carga Horária
```

---

## Critério de Geração Automática

Sistema gera planejamento quando:

```python
if (
    colaborador.avaliacao.nivel < 2        # Nota 0 ou 1
    and colaborador.avaliacao.nivel >= 0   # NÃO é -1 (N/A)
    and not planejamento_ja_existe         # Evitar duplicatas
):
    criar_planejamento(
        origem='MATRIZ',
        disciplina=selecionada,
        procedimento=da_disciplina,
        colaborador=identificado,
        data_prevista=informada,
        status='PLANEJADO'
    )
```

---

## Exemplos de Notas e Significado

| Nota | Valor | Significa | Gera Planejamento? |
|------|-------|-----------|-------------------|
| ⭐ Excelente | 3 | Competente | ❌ NÃO |
| ⭐⭐ Bom | 2 | Satisfatório | ❌ NÃO |
| ⭐⭐⭐ Regular | 1 | Insuficiente | ✅ SIM |
| ⭐⭐⭐⭐ Crítico | 0 | Não Avaliado/Crítico | ✅ SIM |
| N/A | -1 | Não Aplicável | ❌ NÃO |

---

## Dicas de Uso

### ✅ FAÇA

1. **Após avaliar a matriz**, gere automaticamente
   ```
   /procedures/planejamentos/matriz/selecionar/
   ```

2. **Selecione disciplinas prioritárias** primeiro
   (aquelas com mais gaps)

3. **Use datas realistas** para planejamento

4. **Revise antes de confirmar**
   para validar datas/locais/instrutores

5. **Rastreie origem dos planejamentos**
   para reportar cobertura de gaps

### ❌ NÃO FAÇA

1. Não crie manualmente se matriz já gerou

2. Não deixe status como PLANEJADO indefinidamente
   (avance para CONFIRMADO ou CANCELADO)

3. Não tente modificar origem após criação
   (delete e recrie se necessário)

4. Não ignore planejamentos marcados como MATRIZ
   (são high-priority)

---

## Perfis de Usuário Recomendados

### Gerente de RH
```
Acesso:
✓ Visualizar lista completa
✓ Criar planejamentos (LIVRE)
✓ Alterar status
✓ Revisar de matriz
```

### Responsável por Treinamento
```
Acesso:
✓ Gerar da matriz
✓ Confirmar planejamentos
✓ Registrar execução
✓ Análise de cobertura
```

### Administrador
```
Acesso:
✓ Tudo acima +
✓ Deletar planejamentos
✓ Admin Django (edição direta)
✓ Criar DisciplinaProcedimento
```

---

## Troubleshooting Rápido

### Problema: "Nenhuma disciplina com gaps"
```
❌ Não há colaboradores com nota < 2 nesta matriz
✅ Solução: Faça avaliações, aguarde ou escolha outra matriz
```

### Problema: "Planejamento já existe"
```
❌ Sistema evita criar duplicatas
✅ Solução: Edite o existente ou use outra data
```

### Problema: Campo X não aparece
```
❌ Campo oculto por lógica condicional
✅ Solução: Verifique origem selecionada, refresh página
```

### Problema: Não consigo salvar
```
❌ Campos obrigatórios conforme origem faltando
✅ Solução: Veja tabela de "Campos Condicionais" acima
```

---

## Performance

### Consultas Otimizadas
- `select_related()` para ForeignKeys
- `prefetch_related()` para ManyToMany
- Índices em `origem`, `status`, `data_prevista`

### Limites Razoáveis
- Até 10.000 planejamentos em lista
- Geração até 1.000 automaticamente
- Load time < 2 segundos

---

## Integração com Outros Módulos

### Matriz de Habilidades
```
/procedures/matrizes/
├─ Cria disciplinas
├─ Avaliadores preenchem notas
└─ Sistema detecta gaps → gera planejamentos
```

### Colaboradores
```
/rh/colaboradores/
├─ Vinculados aos planejamentos (M2M)
├─ Rastreiam treinamentos realizados
└─ Contribuem para histórico
```

### Procedimentos
```
/procedures/procedimentos/
├─ Associados a disciplinas via DisciplinaProcedimento
├─ Usados em planejamentos (LIVRE ou MATRIZ)
└─ Geram registros de treinamento
```

---

## Segurança e Permissões

### Recomendado
- Usar `@login_required` em todas as views ✓
- Validar `clean()` antes de salvar ✓
- Usar `get_object_or_404` ✓

### Implementado
- ✓ Todas as views requerem login
- ✓ Validação de clean() por origem
- ✓ Query segura sem SQL injection

---

## Resumo Técnico

| Item | Descrição |
|------|-----------|
| **Modelos** | 2 novos/modificados |
| **Views** | 2 novas + 1 mod |
| **Templates** | 2 novos + 1 mod |
| **URLs** | 2 novas |
| **Forms** | 1 modificado |
| **Admin** | 3 novos |
| **Migrations** | 1 criada |
| **Arquivos** | 11 modificados |
| **Documentação** | 3 arquivos |

---

**Desenvolvido para facilitar a automação de treinamentos**
