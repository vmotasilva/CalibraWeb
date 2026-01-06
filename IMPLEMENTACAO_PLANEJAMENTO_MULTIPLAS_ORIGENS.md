# IMPLEMENTAÇÃO: SISTEMA DE PLANEJAMENTO COM MÚLTIPLAS ORIGENS
## Geração Automática de Demanda a partir da Matriz de Habilidades

**Data**: 29 de Dezembro, 2025  
**Status**: ✅ IMPLEMENTADO E TESTADO

---

## 1. RESUMO EXECUTIVO

Foram implementadas funcionalidades para associar **Procedimentos de Treinamento** a **Disciplinas da Matriz de Habilidades**, permitindo a geração automática de demandas de treinamento baseadas em gaps identificados na matriz.

### Objetivos Alcançados:
- ✅ Criar associação entre Procedimentos e Disciplinas  
- ✅ Modificar modelo Planejamento para suportar **3 tipos de origem**  
- ✅ Implementar geração automática de planejamentos a partir de gaps da matriz  
- ✅ Criar interface intuitiva para seleção de origem  

---

## 2. MODELOS CRIADOS/MODIFICADOS

### A. Novo Modelo: `DisciplinaProcedimento`
**Localização**: `procedures/models.py` (linhas 726-761)

```python
class DisciplinaProcedimento(models.Model):
    """Associação entre Disciplinas (Matriz de Habilidades) e Procedimentos de Treinamento."""
    disciplina = ForeignKey(Disciplina)  # FK para Disciplina
    procedimento = ForeignKey(Procedimento)  # FK para Procedimento
    obrigatorio = BooleanField(default=True)  # Marca como obrigatório
    ordem = IntegerField(default=0)  # Sequência de execução
    criado_em = DateTimeField(auto_now_add=True)
    atualizado_em = DateTimeField(auto_now=True)
    
    Meta:
        unique_together = ('disciplina', 'procedimento')
        ordering = ['disciplina', 'ordem']
```

**Funcionalidade**: 
- Permite associar múltiplos procedimentos a uma disciplina
- Define obrigatoriedade e ordem de execução
- Garante unicidade da combinação disciplina-procedimento

---

### B. Modelo Modificado: `PlanejamentoTreinamento`
**Localização**: `procedures/models.py` (linhas 764-848)

#### Novos Campos Adicionados:

1. **`origem`** (CharField com choices)
   ```python
   ORIGEM_CHOICES = [
       ("DEMANDA", "Demanda Existente"),
       ("MATRIZ", "Matriz de Habilidades"),
       ("LIVRE", "Planejamento Livre"),
   ]
   ```
   - Define o tipo/origem do planejamento
   - Determina quais campos são obrigatórios

2. **`disciplina`** (ForeignKey para Disciplina)
   - Preenchido quando origem é "MATRIZ"
   - Rastreia qual disciplina gerou o planejamento
   - nullable e blank=True

#### Campos Existentes Modificados:

- **`procedimento`**: Agora nullable (alguns planejamentos vêm da matriz)
- **Validação**: Método `clean()` valida campos conforme origem

---

## 3. MIGRATIONS CRIADAS

**Arquivo**: `procedures/migrations/0018_planejamentotreinamento_disciplina_and_more.py`

```
- Add field disciplina to planejamentotreinamento
- Add field origem to planejamentotreinamento
- Alter field procedimento on planejamentotreinamento
- Create model DisciplinaProcedimento
```

**Status**: ✅ Aplicada com sucesso

---

## 4. VIEWS IMPLEMENTADAS

### A. `selecionar_matriz_view`
**Localização**: `procedures/views/planejamento_views.py` (linhas 265-283)  
**URL**: `/procedures/planejamentos/matriz/selecionar/`

Exibe lista de matrizes disponíveis para seleção antes de gerar planejamentos.

**Contexto Renderizado**:
- `matrizes`: QuerySet de MatrizHabilidade
- `titulo`: String com título da página

---

### B. `gerar_planejamentos_matriz_view`
**Localização**: `procedures/views/planejamento_views.py` (linhas 286-383)  
**URL**: `/procedures/planejamentos/matriz/<int:matriz_id>/gerar/`

**Fluxo GET**:
1. Exibe formulário com seleção de disciplina
2. Para cada disciplina, conta colaboradores com "gaps" (nível < 2 e ≠ -1)
3. Mostra apenas disciplinas com gaps

**Fluxo POST**:
1. Recebe: `disciplina`, `data_prevista`, `local`
2. Busca colaboradores com avaliação < 2 nesta disciplina
3. Para cada colaborador e cada procedimento associado à disciplina:
   - Verifica se planejamento já existe
   - Cria novo `PlanejamentoTreinamento` com:
     - `origem = 'MATRIZ'`
     - `status = 'PLANEJADO'`
     - Observações com referência ao gap detectado
4. Retorna à lista com mensagem de sucesso

**Lógica de Critério**:
```python
AvaliacaoHabilidade.objects.filter(
    disciplina=disciplina,
    nivel__lt=2,        # Menor que 2
    nivel__gte=0        # Não é -1 (N/A)
)
```

---

## 5. FORMULÁRIOS ATUALIZADOS

### `PlanejamentoTreinamentoForm`
**Localização**: `procedures/forms/forms.py` (linhas 403-465)

#### Campos Adicionados:
- `origem`: RadioSelect com 3 opções
- `disciplina`: Select (condicional)

#### Lógica Condicional (`__init__`):
- Define `required=True/False` dinamicamente conforme origem
- Adiciona help_text explicativos para cada campo

#### Campos no Formulário:
```python
fields = [
    'titulo', 'origem', 'procedimento', 'disciplina', 'colaboradores', 'instrutor',
    'data_prevista', 'data_realizada', 'carga_horaria',
    'local', 'status', 'observacoes'
]
```

---

## 6. TEMPLATES CRIADOS/MODIFICADOS

### A. Novo: `selecionar_matriz.html`
**Localização**: `procedures/templates/procedures/selecionar_matriz.html`

- Lista de matrizes com ícones Bootstrap
- Links diretos para gerar planejamentos
- Exibe quantidade de disciplinas por matriz

**Componentes**:
- Card com lista de matrizes
- Badges com contagem
- Botão voltar para planejamentos

---

### B. Novo: `gerar_planejamentos_matriz.html`
**Localização**: `procedures/templates/procedures/gerar_planejamentos_matriz.html`

- Formulário com select de disciplina
- Data e local de treinamento
- Alerta informativo sobre o processo
- Exibe badges com quantidade de "gaps"

**Funcionalidades**:
- Validação Bootstrap no frontend
- Help texts explicativos
- Resumo do que será criado

---

### C. Modificado: `planejamento_form.html`
**Localização**: `procedures/templates/procedures/planejamento_form.html`

#### Mudanças:
1. **Nova seção**: Campo "origem" em destaque (bg-light, bordered)
2. **Campos condicionais** com JavaScript:
   - Mostra/esconde `procedimento_field` quando origem é "LIVRE"
   - Mostra/esconde `disciplina_field` quando origem é "MATRIZ"
3. **Script JavaScript**: Controla visibilidade e required conforme seleção

**JavaScript Lógica**:
```javascript
if (origem === 'LIVRE') {
    procedimento → required
    disciplina → hidden
} else if (origem === 'MATRIZ') {
    disciplina → required
    procedimento → hidden
} else { // DEMANDA
    ambos → hidden
}
```

---

## 7. ADMIN DJANGO CONFIGURADO

### Classes Adicionadas:

#### `DisciplinaAdmin`
- list_display: `['codigo', 'nome', 'matriz', 'obrigatoriedade_legal', 'ativo']`
- search_fields: `['codigo', 'nome']`
- list_filter: `['matriz', 'obrigatoriedade_legal', 'ativo']`

#### `DisciplinaProcedimentoAdmin`
- list_display: `['disciplina', 'procedimento', 'obrigatorio', 'ordem']`
- search_fields: `['disciplina__nome', 'procedimento__nome']`
- list_filter: `['obrigatorio']`

#### `PlanejamentoTreinamentoAdmin`
- list_display: `['titulo', 'origem', 'data_prevista', 'status']`
- search_fields: `['titulo', 'observacoes']`
- list_filter: `['origem', 'status', 'data_prevista']`
- fieldsets: Organiza campos em grupos lógicos
- filter_horizontal: Para seleção de colaboradores

**Registros**:
```python
admin_site.register(Disciplina, DisciplinaAdmin)
admin_site.register(DisciplinaProcedimento, DisciplinaProcedimentoAdmin)
admin_site.register(PlanejamentoTreinamento, PlanejamentoTreinamentoAdmin)
```

---

## 8. URLS ADICIONADAS

**Arquivo**: `procedures/urls.py` (linhas 147-156)

```python
path('planejamentos/matriz/selecionar/', selecionar_matriz_view, name='selecionar_matriz'),
path('planejamentos/matriz/<int:matriz_id>/gerar/', gerar_planejamentos_matriz_view, name='gerar_planejamentos_matriz'),
```

---

## 9. FLUXO DE UTILIZAÇÃO

### Cenário 1: Planejamento Livre
1. Usuário acessa `/procedures/planejamentos/novo/`
2. Seleciona origem: **"Planejamento Livre"**
3. Form exibe campo `procedimento` (obrigatório)
4. Preenche titulo, colaboradores, datas, instrutor
5. Salva com `status = PLANEJADO`

### Cenário 2: Planejamento pela Matriz
1. Usuário acessa `/procedures/planejamentos/matriz/selecionar/`
2. Seleciona matriz disponível
3. Sistema exibe disciplinas com gaps
4. Usuário seleciona disciplina e data
5. Sistema gera automaticamente:
   - 1 planejamento por procedimento associado
   - Vinculado a cada colaborador com gap
   - Com origem = "MATRIZ"
   - Com observações rastreando o gap

### Cenário 3: Demanda Existente
1. Usuário acessa `/procedures/planejamentos/novo/`
2. Seleciona origem: **"Demanda Existente"**
3. Form exibe apenas campos neutros
4. Preenche informações
5. Salva com rastreamento de origem

---

## 10. CRITÉRIOS DE GERAÇÃO AUTOMÁTICA

### Disciplinas com "Gap"
```python
AvaliacaoHabilidade.objects.filter(
    disciplina=disciplina,
    nivel__lt=2,          # Notas 0 ou 1
    nivel__gte=0          # Excluir -1 (N/A)
)
```

### Evitar Duplicação
```python
if not PlanejamentoTreinamento.objects.filter(
    origem='MATRIZ',
    disciplina=disciplina,
    procedimento=procedimento,
    colaboradores=colaborador,
    status__in=['PLANEJADO', 'CONFIRMADO']
).exists():
    # Criar novo
```

---

## 11. CAMPOS E DADOS PERSISTIDOS

### Quando origem = "MATRIZ":
- `origem = 'MATRIZ'`
- `disciplina` preenchido
- `procedimento` preenchido (do relacionamento)
- `observacoes` com contexto do gap
- Colaborador vinculado (M2M)

### Quando origem = "LIVRE":
- `origem = 'LIVRE'`
- `procedimento` preenchido
- `disciplina = NULL`
- Colaboradores e instrutor segundo usuário

### Quando origem = "DEMANDA":
- `origem = 'DEMANDA'`
- Ambos procedimento e disciplina podem ser NULL
- Usado quando demanda vem de outra fonte

---

## 12. MELHORIAS FUTURAS

1. **Relatórios**: Dashboard de gaps vs. planejamentos gerados
2. **Histórico**: Rastrear qual gap gerou qual planejamento
3. **Priorização**: Classificar automaticamente por urgência
4. **Notificações**: Alertar gestores sobre gaps não cobertos
5. **Exportação**: Gerar plano em PDF com todos os planejamentos
6. **Integração de Demandas**: Modelo DemandaTreinamento integrado

---

## 13. VALIDAÇÃO E TESTES

### Testes Manuais Executados:
✅ Criação de DisciplinaProcedimento no admin  
✅ Filtro de disciplinas com gaps  
✅ Geração de planejamentos múltiplos  
✅ Validação de campos conforme origem  
✅ Visibilidade condicional no template  

### Warnings Existentes (Não Bloqueantes):
- ⚠️ Duplicate custom_filters template tags (entre procedures e qms)
- Não afeta funcionalidade

---

## 14. ARQUIVOS MODIFICADOS

| Arquivo | Tipo | Alteração |
|---------|------|-----------|
| `procedures/models.py` | Model | ✅ +2 modelos |
| `procedures/admin.py` | Admin | ✅ +3 classes |
| `procedures/views/planejamento_views.py` | View | ✅ +2 funções |
| `procedures/forms/forms.py` | Form | ✅ Modificado |
| `procedures/urls.py` | URL | ✅ +2 rotas |
| `procedures/templates/procedures/planejamento_form.html` | Template | ✅ Atualizado |
| `procedures/templates/procedures/selecionar_matriz.html` | Template | ✅ Novo |
| `procedures/templates/procedures/gerar_planejamentos_matriz.html` | Template | ✅ Novo |
| `procedures/migrations/0018_*.py` | Migration | ✅ Criada |

---

## 15. COMMITS RECOMENDADOS

```bash
git add procedures/
git commit -m "feat: Implementar sistema de planejamento com múltiplas origens

- Criar modelo DisciplinaProcedimento para associar procedimentos a disciplinas
- Estender PlanejamentoTreinamento com 3 tipos de origem (LIVRE, MATRIZ, DEMANDA)
- Implementar geração automática de planejamentos a partir de gaps da matriz
- Adicionar views para seleção de matriz e geração de demandas
- Criar templates para interface de múltiplas origens
- Registrar novos modelos no admin Django
- Adicionar rotas para fluxo de geração automática

Benefícios:
- Automação de detecção de gaps em treinamentos
- Rastreabilidade de origem dos planejamentos
- Interface intuitiva com campos condicionais
- Integração direta com matriz de habilidades
"
```

---

## 16. PRÓXIMOS PASSOS

1. **Testar em Produção**: Deploy das mudanças
2. **Documentar para Usuários**: Criar guia de uso
3. **Feedback**: Coletar feedback dos stakeholders
4. **Melhorias Iterativas**: Refinamentos conforme necessidade

---

**Desenvolvido com ✨ atenção aos detalhes**
