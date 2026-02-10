# 🔧 Especificações Técnicas - Módulo de Soluções

## 📐 Arquitetura de Banco de Dados

### Diagrama de Relacionamentos

```
┌─────────────────────┐
│  AcaoCorretiva      │
├─────────────────────┤
│ id (PK)             │
│ numero_registro     │
│ titulo              │
│ tipo                │
│ status              │
│ prioridade          │
│ data_abertura       │
│ data_vencimento     │
│ data_conclusao      │
│ responsavel (FK)    │
│ criado_por (FK)     │
│ ...                 │
└──────────┬──────────┘
           │ 1:N
           │
┌──────────┴─────────────────────┐
│        Solucao                  │
├─────────────────────────────────┤
│ id (PK)                         │
│ acao_corretiva (FK)             │
│ tipo (choice)                   │
│ titulo                          │
│ descricao                       │
│ status                          │
│ responsavel (FK)                │
│ data_criacao                    │
│ data_inicio                     │
│ data_conclusao                  │
│ ativo                           │
└─────────────┬─────────────────┬─────────────────┬──────────────────┬──────────────────┬─────────────────┘
              │                 │                 │                  │                  │
        (1:1) │            (1:1) │            (1:1) │             (1:1) │             (1:1) │            (1:1) │
              │                 │                 │                  │                  │
    ┌─────────▼────────┐ ┌──────▼────────┐ ┌────▼─────────┐ ┌───────▼──────────┐ ┌────▼─────────────────┐ ┌──▼──────────────┐
    │   PlanoAcao      │ │   SolucaoA3    │ │  Solucao8D   │ │  SolucaoRNC      │ │ SolucaoGestaoDeMuda  │ │ RevisaoGerencial │
    ├──────────────────┤ ├────────────────┤ ├──────────────┤ ├──────────────────┤ ├──────────────────────┤ ├──────────────────┤
    │ solucao (FK)     │ │ solucao (FK)    │ │ solucao (FK) │ │ solucao (FK)     │ │ solucao (FK)         │ │ solucao (FK)     │
    │ acao_proposta    │ │ problema_*      │ │ d1_time      │ │ nc_descricao     │ │ mudanca_descricao    │ │ revisao_*        │
    │ responsavel_acao │ │ analise_*       │ │ d2_*         │ │ nc_tipo          │ │ motivacao            │ │ escopo           │
    │ data_inicio      │ │ causa_raiz      │ │ d3_*         │ │ acao_imediata    │ │ impacto_processos    │ │ achados_*        │
    │ data_conclusao   │ │ contramedidas   │ │ d4_*         │ │ acao_corretiva   │ │ impacto_sistemas     │ │ recomendacoes    │
    │ status           │ │ resultados_*    │ │ d5_*         │ │ acao_preventiva  │ │ plano_implementacao  │ │ prioridade_*     │
    │ resultado        │ │ verificacao     │ │ d6_*         │ │ verificacao      │ │ data_implementacao   │ │ plano_acao       │
    │                  │ │ resultado_verif │ │ d7_*         │ │ resultado        │ │ status               │ │ responsavel_*    │
    │                  │ │                 │ │ d8_*         │ │                  │ │ validacao_*          │ │ data_alvo_*      │
    │                  │ │                 │ │              │ │                  │ │                      │ │ resultado        │
    │                  │ │                 │ │              │ │                  │ │                      │ │ data_conclusao   │
    └──────────────────┘ └────────────────┘ └──────────────┘ └──────────────────┘ └──────────────────────┘ └──────────────────┘
```

---

## 📝 Definição de Campos

### Solucao (Modelo Base)

```python
class Solucao(models.Model):
    TIPO_SOLUCAO_CHOICES = [
        ('plano_acao', 'Plano de Ação'),           # Simples
        ('a3', 'A3'),                               # TPS - Toyota
        ('8d', '8D'),                               # Ford - Complexo
        ('rnc', 'RNC'),                             # ISO 9001
        ('gestao_mudanca', 'Gestão de Mudança'),   # Mudanças
        ('revisao_gerencial', 'Revisão Gerencial'), # Estratégia
    ]
    
    STATUS_CHOICES = [
        ('planejamento', 'Planejamento'),     # Inicial
        ('analise', 'Análise'),               # Em análise
        ('implementacao', 'Implementação'),   # Sendo executada
        ('validacao', 'Validação'),           # Validando resultados
        ('encerrada', 'Encerrada'),           # Finalizada
    ]
    
    # Campos obrigatórios
    acao_corretiva: ForeignKey              # Sempre vinculada a uma ação
    tipo: CharField                         # Um dos 6 tipos acima
    titulo: CharField(max_length=200)       # Identificação
    descricao: TextField                    # Detalhes
    status: CharField                       # Estado atual
    
    # Campos opcionais
    data_criacao: DateTimeField             # Auto-preenchido
    data_inicio: DateField                  # Quando começar
    data_conclusao: DateField               # Quando terminar
    responsavel: ForeignKey(Colaborador)    # Quem lidera
    ativo: BooleanField                     # Ativo ou arquivado
```

---

## 🏗️ Views (Lógica de Negócio)

### `listar_solucoes(request)`

**Propósito:** Listar todas as soluções com filtros

**Filtros Disponíveis:**
- `tipo`: Filtra por tipo de solução (6 opções)
- `status`: Filtra por status (5 estados)
- `busca`: Busca por título ou descrição (Q objects)

**Retorna:**
- Lista paginada de soluções
- Contagem por tipo (para cards)
- Contexto com filtros aplicados

**Template:** `listar_solucoes.html`

```python
GET /acoes/solucoes/                          # Sem filtros
GET /acoes/solucoes/?tipo=8d                  # Apenas 8D
GET /acoes/solucoes/?status=implementacao     # Em implementação
GET /acoes/solucoes/?busca=defeito            # Busca por "defeito"
GET /acoes/solucoes/?tipo=a3&status=validacao # Combinado
```

### `detalhe_solucao(request, solucao_id)`

**Propósito:** Mostrar detalhes completos da solução

**Lógica:**
1. Recupera solução base
2. Identifica tipo
3. Carrega modelo específico (PlanoAcao, A3, 8D, etc.)
4. Renderiza template específico

**Template:** `detalhe_solucao.html` (dinâmico por tipo)

```python
GET /acoes/solucao/1/                        # ID da solução
```

**Estrutura da Página:**
- Cabeçalho com titulo e badges
- Seção de informações básicas
- Seção específica por tipo (conteúdo diferente)
- Painel lateral com resumo e ações

### `criar_solucao(request, acao_id)`

**Propósito:** Criar nova solução vinculada a ação

**Fluxo:**
1. GET: Exibe página com 6 cards de tipos
2. POST: Recebe tipo, cria Solucao base + modelo específico

**POST Parameters:**
```
tipo: ['plano_acao', 'a3', '8d', 'rnc', 'gestao_mudanca', 'revisao_gerencial']
titulo: string
descricao: string
responsavel: FK (Colaborador)
[campos específicos por tipo]
```

**Redirecionamento:** Para detalhes da solução criada

```python
POST /acoes/acao/5/solucao/criar/
GET /acoes/solucao/12/                       # Redirecionado após criar
```

### `editar_solucao(request, solucao_id)`

**Propósito:** Editar solução existente

**Funcionalidade:**
1. GET: Carrega formulário com dados atuais
2. POST: Atualiza solução base + modelo específico

**Limitações Atuais:**
- Tipo de solução não pode ser alterado (seria quebrar integridade)
- Apenas campos básicos da Solucao são editáveis
- Modelo específico editável com mais trabalho

```python
GET /acoes/solucao/12/editar/                # Carregar formulário
POST /acoes/solucao/12/editar/               # Salvar alterações
```

---

## 🎨 Templates (Apresentação)

### `listar_solucoes.html`

**Componentes:**
1. **Cards de Contagem** (6 cards coloridos)
   - Plano de Ação (azul)
   - A3 (ciano)
   - 8D (verde)
   - RNC (amarelo)
   - Gestão de Mudança (vermelho)
   - Revisão Gerencial (cinza)

2. **Formulário de Filtros**
   - Campo busca (titulo/descricao)
   - Dropdown tipo (7 opções: Todos + 6 tipos)
   - Dropdown status (6 opções: Todos + 5 status)
   - Botões Filtrar/Limpar

3. **Tabela Responsiva**
   - Colunas: Título | Tipo | Ação Relacionada | Status | Responsável | Data | Ações
   - Sticky header
   - Badges coloridas
   - Ícones de ação (olho, lápis)

4. **Estado Vazio**
   - Mensagem quando nenhuma solução encontrada

### `detalhe_solucao.html`

**Estrutura Dinâmica (varia por tipo):**

**Para Plano de Ação:**
```
├── Informações Básicas
├── Detalhes do Plano de Ação
│   ├── Ação Proposta
│   ├── Responsável pela Ação
│   ├── Datas (início/conclusão)
│   ├── Status
│   └── Resultado
└── Painel Lateral (info + ações)
```

**Para A3:**
```
├── Informações Básicas
├── Relatório A3
│   ├── Problema (descrição + impacto)
│   ├── Situação Atual
│   ├── Análise de Causas
│   ├── Causa Raiz
│   ├── Contramedidas
│   ├── Resultados Esperados
│   └── Verificação
└── Painel Lateral
```

**Para 8D:**
```
├── Informações Básicas
├── 8 Disciplinas
│   ├── D1 - Time
│   ├── D2 - Problema
│   ├── D3 - Contenção
│   ├── D4 - Causa Raiz
│   ├── D5 - Contramedidas
│   ├── D6 - Implementação
│   ├── D7 - Verificação
│   └── D8 - Padronização
└── Painel Lateral
```

(Similar para RNC, Gestão de Mudança, Revisão Gerencial)

---

## 🔌 Integração com Admin Django

### `SolucaoAdmin`

```python
list_display: (
    'titulo',           # Título principal
    'get_tipo_display', # Tipo legível
    'acao_corretiva',   # Qual ação
    'status',           # Estado
    'responsavel',      # Quem lidera
    'data_criacao'      # Data
)

list_filter: ('tipo', 'status', 'data_criacao')

search_fields: ('titulo', 'descricao', 'acao_corretiva__numero_registro')

fieldsets: (
    ('Relacionamento', {'fields': ('acao_corretiva',)}),
    ('Informações Básicas', {'fields': ('tipo', 'titulo', 'descricao', 'status')}),
    ('Datas', {'fields': ('data_inicio', 'data_conclusao')}),
    ('Responsáveis', {'fields': ('responsavel',)}),
    ('Status', {'fields': ('ativo',)}),
)
```

### Admins Específicos para Cada Tipo

Cada tipo tem seu próprio `Admin` com fieldsets customizados:
- `PlanoAcaoAdmin`: Agrupa campos de plano
- `SolucaoA3Admin`: Organiza em Problema → Análise → Solução
- `Solucao8DAdmin`: 8 fieldsets (um por D)
- `SolucaoRNCAdmin`: Agrupa conforme ISO 9001
- `SolucaoGestaoDeMudancaAdmin`: Agrupa por impacto
- `RevisaoGerencialAdmin`: Agrupa por fase

---

## 📡 Endpoints da API

### URLs Configuradas

```python
app_name = 'acoes'

urlpatterns = [
    # Ações Corretivas
    path('', listar_acoes, name='listar_acoes'),
    path('acao/<int:acao_id>/', detalhe_acao, name='detalhe_acao'),
    
    # Soluções
    path('solucoes/', listar_solucoes, name='listar_solucoes'),
    path('solucao/<int:solucao_id>/', detalhe_solucao, name='detalhe_solucao'),
    path('acao/<int:acao_id>/solucao/criar/', criar_solucao, name='criar_solucao'),
    path('solucao/<int:solucao_id>/editar/', editar_solucao, name='editar_solucao'),
]
```

---

## 🗂️ Estrutura de Arquivos

```
acoes/
├── __init__.py
├── models.py                              # 7 modelos (base + 6 tipos)
├── views.py                               # Views de ações
├── views_solucoes.py                      # Views de soluções
├── urls.py                                # URL routing
├── admin.py                               # Admin Django
├── apps.py                                # App config
├── tests.py                               # (Opcional)
├── migrations/
│   ├── 0001_initial.py
│   ├── 0002_*.py
│   └── 0003_solucao_*.py                 # Novos modelos
├── templates/
│   └── acoes/
│       ├── listar_acoes.html
│       ├── detalhe_acao.html
│       ├── listar_solucoes.html           # ✨ Nova
│       ├── detalhe_solucao.html           # ✨ Nova
│       ├── criar_solucao.html             # ✨ Nova
│       └── editar_solucao.html            # ✨ Nova
└── static/                                 # (Se necessário)
```

---

## 🔐 Segurança & Permissões

### Proteções Aplicadas

1. **@login_required:** Todas as views requerem autenticação
2. **ForeignKey Validations:** Django verifica integridade
3. **CSRF Protection:** Token CSRF em todos os forms
4. **SQL Injection Prevention:** ORM Django impede injeção
5. **XSS Prevention:** Templates escapam HTML automaticamente

### Permissões Sugeridas (Futuro)

```python
# Seria interessante adicionar:
- view_solucao: Qualquer um pode visualizar
- add_solucao: Apenas gerentes/qualidade
- change_solucao: Apenas responsável + gerente
- delete_solucao: Apenas admin
```

---

## 📊 Performance & Otimizações

### Queries Otimizadas

```python
# Em listar_solucoes()
solucoes = Solucao.objects.select_related('acao_corretiva', 'responsavel')
# Reduz N queries a 1 query por relacionamento

# Filtros eficientes
if tipo_filter:
    solucoes = solucoes.filter(tipo=tipo_filter)  # Index no banco

if busca:
    solucoes = solucoes.filter(
        Q(titulo__icontains=busca) | Q(descricao__icontains=busca)
    )  # Full-text seria ideal para produção
```

### Índices no Banco

```python
# Solucao model tem default indexes em:
- PK (id) - automático
- acao_corretiva - relacionamento
- tipo - filtro comum
- status - filtro comum
- responsavel - filtro comum
```

### Sugestões de Melhoria

1. Adicionar paginação em `listar_solucoes()` (20-50 por página)
2. Cache de contagens (recompute a cada hora)
3. Índices de busca full-text em PostgreSQL
4. Lazy loading de templates para muitas soluções

---

## 🧪 Testes (Recomendado)

### Unit Tests Sugeridos

```python
# test_models.py
- test_solucao_str_representation()
- test_plano_acao_creation()
- test_a3_creation_with_all_fields()
- test_8d_disciplina_sequence()
- test_rnc_type_choices()
- test_mudanca_implementation_date()
- test_revisao_recommendations()

# test_views.py
- test_listar_solucoes_filters()
- test_criar_solucao_valid_data()
- test_criar_solucao_invalid_type()
- test_detalhe_solucao_correct_template()
- test_editar_solucao_saves_correctly()

# test_admin.py
- test_admin_list_display()
- test_admin_filter_options()
- test_admin_search_fields()
```

---

## 📋 Changelog

### v1.0 (10/02/2025)
- ✅ Modelos para 6 tipos de solução
- ✅ Views CRUD completas
- ✅ Templates com design responsivo
- ✅ Admin Django totalmente configurado
- ✅ Integração com menu navbar
- ✅ Documentação completa

### v1.1 (Planejado)
- Adicionar permissões granulares
- Sistema de aprovação de mudanças
- Comentários e discussão
- Upload de anexos

---

## 🚀 Deployment

### Passos de Deploy

1. **Ambiente Local:**
   ```bash
   python manage.py makemigrations acoes
   python manage.py migrate acoes
   python manage.py test acoes/
   python manage.py runserver
   ```

2. **Produção (Railway):**
   ```bash
   git add -A
   git commit -m "feat: novo módulo de soluções"
   git push origin main
   # Railway detecta e faz deploy automaticamente
   # Migrations rodam automaticamente
   ```

3. **Verificação:**
   - Acessar https://seu-dominio.com/acoes/solucoes/
   - Verificar menu dropdown em Ações Corretivas
   - Criar teste solução
   - Verificar admin em /admin/acoes/

---

**Documento de Referência Técnica**  
**Versão:** 1.0  
**Data:** 10 de fevereiro de 2025
