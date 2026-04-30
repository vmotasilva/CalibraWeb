# REFERÊNCIA TÉCNICA: ESTRUTURA DE DADOS E QUERIES

## 1. ESTRUTURA DE TABELAS

### Tabela: `procedures_disciplinaprocedimento`

```sql
CREATE TABLE procedures_disciplinaprocedimento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disciplina_id INTEGER NOT NULL,
    procedimento_id INTEGER NOT NULL,
    obrigatorio BOOLEAN NOT NULL DEFAULT 1,
    ordem INTEGER NOT NULL DEFAULT 0,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NOT NULL,
    
    FOREIGN KEY (disciplina_id) REFERENCES procedures_disciplina(id) ON DELETE CASCADE,
    FOREIGN KEY (procedimento_id) REFERENCES procedures_procedimento(id) ON DELETE CASCADE,
    UNIQUE(disciplina_id, procedimento_id)
);

CREATE INDEX idx_disciplina ON procedures_disciplinaprocedimento(disciplina_id);
CREATE INDEX idx_procedimento ON procedures_disciplinaprocedimento(procedimento_id);
```

---

### Tabela: `procedures_planejamentotreinamento` (Modificada)

```sql
-- Novos campos adicionados:

ALTER TABLE procedures_planejamentotreinamento ADD COLUMN origem VARCHAR(20);
ALTER TABLE procedures_planejamentotreinamento ADD COLUMN disciplina_id INTEGER;

ALTER TABLE procedures_planejamentotreinamento
ADD CONSTRAINT fk_disciplina
FOREIGN KEY (disciplina_id) REFERENCES procedures_disciplina(id) ON DELETE SET NULL;

-- Campos existentes alterados:
ALTER TABLE procedures_planejamentotreinamento 
MODIFY COLUMN procedimento_id INTEGER NULL;  -- Agora aceita NULL

CREATE INDEX idx_origem ON procedures_planejamentotreinamento(origem);
CREATE INDEX idx_status_data ON procedures_planejamentotreinamento(status, data_prevista);
```

---

### Tabela: `procedures_planejamentotreinamento_colaboradores` (Existente, sem mudança)

```sql
-- M2M entre PlanejamentoTreinamento e Colaborador
CREATE TABLE procedures_planejamentotreinamento_colaboradores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planejamentotreinamento_id INTEGER NOT NULL,
    colaborador_id INTEGER NOT NULL,
    
    UNIQUE(planejamentotreinamento_id, colaborador_id),
    FOREIGN KEY (planejamentotreinamento_id) REFERENCES procedures_planejamentotreinamento(id),
    FOREIGN KEY (colaborador_id) REFERENCES rh_colaborador(id)
);
```

---

## 2. QUERIES UTILIZADAS

### Query 1: Encontrar Disciplinas com Gaps

```sql
SELECT DISTINCT d.id, d.codigo, d.nome, COUNT(DISTINCT ah.colaborador_id) as gaps_count
FROM procedures_disciplina d
INNER JOIN procedures_avaliacaohabilidade ah ON ah.disciplina_id = d.id
WHERE d.matriz_id = ?
  AND ah.nivel < 2
  AND ah.nivel >= 0
  AND d.ativo = 1
GROUP BY d.id
ORDER BY d.codigo;
```

**Python Django Equivalente**:
```python
from django.db.models import Count

gaps = (AvaliacaoHabilidade.objects
    .filter(
        disciplina__matriz_id=matriz_id,
        nivel__lt=2,
        nivel__gte=0,
        disciplina__ativo=True
    )
    .values('disciplina')
    .annotate(gaps_count=Count('colaborador', distinct=True))
    .order_by('disciplina__codigo'))
```

---

### Query 2: Listar Colaboradores com Gap em Disciplina

```sql
SELECT DISTINCT ah.colaborador_id, c.nome_completo
FROM procedures_avaliacaohabilidade ah
INNER JOIN rh_colaborador c ON c.id = ah.colaborador_id
WHERE ah.disciplina_id = ?
  AND ah.nivel < 2
  AND ah.nivel >= 0
ORDER BY c.nome_completo;
```

**Python Django Equivalente**:
```python
AvaliacaoHabilidade.objects.filter(
    disciplina_id=disciplina_id,
    nivel__lt=2,
    nivel__gte=0
).select_related('colaborador').values_list('colaborador_id', 'colaborador__nome_completo')
```

---

### Query 3: Procedimentos de uma Disciplina

```sql
SELECT p.id, p.codigo, p.nome
FROM procedures_disciplinaprocedimento dp
INNER JOIN procedures_procedimento p ON p.id = dp.procedimento_id
WHERE dp.disciplina_id = ?
  AND dp.obrigatorio = 1
ORDER BY dp.ordem, p.codigo;
```

**Python Django Equivalente**:
```python
Procedimento.objects.filter(
    disciplinas_associadas__disciplina_id=disciplina_id,
    disciplinas_associadas__obrigatorio=True
).order_by(
    'disciplinas_associadas__ordem',
    'codigo'
).distinct()
```

---

### Query 4: Verificar Duplicação de Planejamento

```sql
SELECT COUNT(*) as exists
FROM procedures_planejamentotreinamento pt
INNER JOIN procedures_planejamentotreinamento_colaboradores ptc 
    ON ptc.planejamentotreinamento_id = pt.id
WHERE pt.origem = 'MATRIZ'
  AND pt.disciplina_id = ?
  AND pt.procedimento_id = ?
  AND ptc.colaborador_id = ?
  AND pt.status IN ('PLANEJADO', 'CONFIRMADO');
```

**Python Django Equivalente**:
```python
PlanejamentoTreinamento.objects.filter(
    origem='MATRIZ',
    disciplina_id=disciplina_id,
    procedimento_id=procedimento_id,
    colaboradores__id=colaborador_id,
    status__in=['PLANEJADO', 'CONFIRMADO']
).exists()
```

---

### Query 5: Listar Planejamentos da Matriz

```sql
SELECT pt.*, COUNT(ptc.colaborador_id) as num_colaboradores
FROM procedures_planejamentotreinamento pt
LEFT JOIN procedures_planejamentotreinamento_colaboradores ptc 
    ON ptc.planejamentotreinamento_id = pt.id
WHERE pt.origem = 'MATRIZ'
  AND pt.data_prevista >= CURRENT_DATE
GROUP BY pt.id
ORDER BY pt.data_prevista DESC;
```

**Python Django Equivalente**:
```python
PlanejamentoTreinamento.objects.filter(
    origem='MATRIZ',
    data_prevista__gte=timezone.now().date()
).select_related(
    'disciplina', 'procedimento', 'instrutor'
).prefetch_related(
    'colaboradores'
).annotate(
    num_colaboradores=Count('colaboradores', distinct=True)
).order_by('-data_prevista')
```

---

### Query 6: Relatório de Cobertura

```sql
SELECT 
    d.codigo, d.nome,
    COUNT(DISTINCT ah.colaborador_id) as total_gaps,
    COUNT(DISTINCT CASE 
        WHEN pt.id IS NOT NULL THEN ah.colaborador_id 
    END) as cobertos,
    ROUND(100.0 * COUNT(DISTINCT CASE 
        WHEN pt.id IS NOT NULL THEN ah.colaborador_id 
    END) / COUNT(DISTINCT ah.colaborador_id), 2) as percentual
FROM procedures_disciplina d
LEFT JOIN procedures_avaliacaohabilidade ah ON ah.disciplina_id = d.id
    AND ah.nivel < 2 AND ah.nivel >= 0
LEFT JOIN procedures_planejamentotreinamento pt ON pt.disciplina_id = d.id
    AND pt.origem = 'MATRIZ'
    AND pt.colaboradores.id = ah.colaborador_id
    AND pt.status IN ('PLANEJADO', 'CONFIRMADO', 'REALIZADO')
WHERE d.matriz_id = ?
GROUP BY d.id
ORDER BY percentual ASC;
```

**Python Django Equivalente (Complexo)**:
```python
# Seria necessário fazer em Python após queries
disciplinas = Disciplina.objects.filter(matriz_id=matriz_id)
for disciplina in disciplinas:
    gaps = AvaliacaoHabilidade.objects.filter(
        disciplina=disciplina,
        nivel__lt=2,
        nivel__gte=0
    ).values_list('colaborador_id', flat=True).distinct()
    
    cobertos = PlanejamentoTreinamento.objects.filter(
        origem='MATRIZ',
        disciplina=disciplina,
        status__in=['PLANEJADO', 'CONFIRMADO', 'REALIZADO'],
        colaboradores__id__in=gaps
    ).values_list('colaboradores__id', flat=True).distinct().count()
    
    percentual = (cobertos / len(gaps) * 100) if gaps else 0
```

---

### Query 7: Histórico de Mudanças de Status

```sql
SELECT pt.id, pt.titulo, pt.status, pt.atualizado_em
FROM procedures_planejamentotreinamento pt
WHERE pt.origem = 'MATRIZ'
  AND pt.atualizado_em >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
ORDER BY pt.atualizado_em DESC;
```

**Python Django Equivalente**:
```python
from datetime import timedelta

PlanejamentoTreinamento.objects.filter(
    origem='MATRIZ',
    atualizado_em__gte=timezone.now() - timedelta(days=30)
).order_by('-atualizado_em')
```

---

## 3. ÍNDICES RECOMENDADOS

```sql
-- Melhoram performance de queries
CREATE INDEX idx_planejamento_origem_status 
ON procedures_planejamentotreinamento(origem, status);

CREATE INDEX idx_planejamento_data_prevista 
ON procedures_planejamentotreinamento(data_prevista);

CREATE INDEX idx_avaliacao_nivel 
ON procedures_avaliacaohabilidade(nivel);

CREATE INDEX idx_avaliacao_disciplina 
ON procedures_avaliacaohabilidade(disciplina_id);

CREATE INDEX idx_disciplina_matriz 
ON procedures_disciplina(matriz_id);
```

---

## 4. RELATÓRIOS ÚTEIS

### Relatório 1: Gaps por Disciplina

```python
# View para gerar relatório
def relatorio_gaps_por_disciplina(matriz_id):
    disciplinas = Disciplina.objects.filter(matriz_id=matriz_id)
    
    resultado = []
    for d in disciplinas:
        gaps = AvaliacaoHabilidade.objects.filter(
            disciplina=d,
            nivel__lt=2,
            nivel__gte=0
        ).count()
        
        planejados = PlanejamentoTreinamento.objects.filter(
            origem='MATRIZ',
            disciplina=d,
            status='PLANEJADO'
        ).count()
        
        resultado.append({
            'disciplina': d.nome,
            'gaps': gaps,
            'planejados': planejados,
            'cobertura': f"{planejados / gaps * 100:.1f}%" if gaps > 0 else "0%"
        })
    
    return resultado
```

---

### Relatório 2: Cronograma de Treinamentos

```python
def cronograma_treinamentos(data_inicio, data_fim):
    planejamentos = PlanejamentoTreinamento.objects.filter(
        data_prevista__range=[data_inicio, data_fim]
    ).select_related(
        'disciplina', 'procedimento', 'instrutor'
    ).prefetch_related('colaboradores').order_by('data_prevista')
    
    cronograma = {}
    for p in planejamentos:
        data = p.data_prevista
        if data not in cronograma:
            cronograma[data] = []
        
        cronograma[data].append({
            'titulo': p.titulo,
            'origem': p.get_origem_display(),
            'colaboradores': p.colaboradores.count(),
            'local': p.local or 'A confirmar',
            'instrutor': p.instrutor.nome_completo if p.instrutor else 'Sem instrutor'
        })
    
    return cronograma
```

---

### Relatório 3: Efetividade de Treinamentos

```python
def efetividade_treinamentos(data_inicio, data_fim):
    planejamentos = PlanejamentoTreinamento.objects.filter(
        data_realizada__range=[data_inicio, data_fim]
    )
    
    total = planejamentos.count()
    realizado = planejamentos.filter(status='REALIZADO').count()
    cancelado = planejamentos.filter(status='CANCELADO').count()
    confirmado = planejamentos.filter(status='CONFIRMADO').count()
    
    return {
        'total_planejado': total,
        'realizado': realizado,
        'cancelado': cancelado,
        'confirmado': confirmado,
        'taxa_execucao': f"{realizado / total * 100:.1f}%" if total > 0 else "0%"
    }
```

---

## 5. CONSTRAINTS E VALIDAÇÕES

### Level 1: Database Level (SQL)
```sql
-- Unique constraint evita duplicação
UNIQUE(disciplina_id, procedimento_id)

-- Foreign keys garantem integridade
FOREIGN KEY (disciplina_id) REFERENCES procedures_disciplina(id)
FOREIGN KEY (procedimento_id) REFERENCES procedures_procedimento(id)

-- NOT NULL em campos obrigatórios
origen VARCHAR(20) NOT NULL
titulo VARCHAR(200) NOT NULL
```

### Level 2: Model Level (Django)
```python
class PlanejamentoTreinamento(models.Model):
    def clean(self):
        # Validação conforme origem
        if self.origem == "MATRIZ" and not self.disciplina:
            raise ValidationError("Disciplina obrigatória para MATRIZ")
```

### Level 3: Form Level (Django)
```python
class PlanejamentoTreinamentoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Definir required conforme origem
        if self.instance.origem == 'LIVRE':
            self.fields['procedimento'].required = True
```

### Level 4: View Level (Django)
```python
def gerar_planejamentos_matriz_view(request, matriz_id):
    # Validar disciplina pertence à matriz
    disciplina = get_object_or_404(Disciplina, id=disciplina_id, matriz=matriz)
    
    # Evitar duplicação
    if not PlanejamentoTreinamento.objects.filter(...).exists():
        # Criar novo
```

---

## 6. OTIMIZAÇÕES DE PERFORMANCE

### Select Related (FK)
```python
# ❌ RUIM: N+1 queries
planejamentos = PlanejamentoTreinamento.objects.all()
for p in planejamentos:
    print(p.disciplina.nome)  # Query por item

# ✅ BOM: 1 query com join
planejamentos = PlanejamentoTreinamento.objects.select_related('disciplina')
```

### Prefetch Related (M2M)
```python
# ❌ RUIM: N+1 queries
planejamentos = PlanejamentoTreinamento.objects.all()
for p in planejamentos:
    print(p.colaboradores.count())  # Query por item

# ✅ BOM: 1 query com join
planejamentos = PlanejamentoTreinamento.objects.prefetch_related('colaboradores')
```

### Aggregation
```python
# ❌ RUIM: Múltiplas queries
gaps_por_disciplina = {}
for d in disciplinas:
    gaps_por_disciplina[d.id] = AvaliacaoHabilidade.objects.filter(
        disciplina=d,
        nivel__lt=2
    ).count()

# ✅ BOM: 1 query com agregação
from django.db.models import Count
gaps = (AvaliacaoHabilidade.objects
    .filter(nivel__lt=2)
    .values('disciplina_id')
    .annotate(count=Count('id')))
```

---

## 7. EXEMPLO DE EXECUÇÃO

### Cenário Completo em SQL

```sql
-- 1. Matriz: "Calibração"
SELECT * FROM procedures_matrizabilidade WHERE nome LIKE 'Calibra%';
-- Result: id=1

-- 2. Disciplinas da Matriz
SELECT * FROM procedures_disciplina WHERE matriz_id=1 AND ativo=1;
-- Result: id=10 (Balança), id=11 (Micrômetro), id=12 (Paquímetro)

-- 3. Gaps em Balança (id=10)
SELECT DISTINCT ah.colaborador_id, c.nome_completo, ah.nivel
FROM procedures_avaliacaohabilidade ah
INNER JOIN rh_colaborador c ON c.id = ah.colaborador_id
WHERE ah.disciplina_id=10 AND ah.nivel < 2 AND ah.nivel >= 0;
-- Result: colab_id=5 (Ana, nota=1), colab_id=7 (Carlos, nota=0)

-- 4. Procedimentos de Balança
SELECT p.id, p.codigo FROM procedures_disciplinaprocedimento dp
INNER JOIN procedures_procedimento p ON p.id = dp.procedimento_id
WHERE dp.disciplina_id=10;
-- Result: proc_id=100 (P-BAL-001), proc_id=101 (P-BAL-002)

-- 5. Criar Planejamentos
INSERT INTO procedures_planejamentotreinamento 
(titulo, origem, procedimento_id, disciplina_id, data_prevista, status)
VALUES 
('Calibração Balança - P-BAL-001', 'MATRIZ', 100, 10, '2026-01-15', 'PLANEJADO'),
('Calibração Balança - P-BAL-001', 'MATRIZ', 100, 10, '2026-01-15', 'PLANEJADO'),
('Calibração Balança - P-BAL-002', 'MATRIZ', 101, 10, '2026-01-15', 'PLANEJADO'),
('Calibração Balança - P-BAL-002', 'MATRIZ', 101, 10, '2026-01-15', 'PLANEJADO');

-- 6. Vincular Colaboradores
INSERT INTO procedures_planejamentotreinamento_colaboradores 
(planejamentotreinamento_id, colaborador_id) VALUES
(1, 5), (2, 7), (3, 5), (4, 7);

-- Result: 4 planejamentos criados (2 colaboradores × 2 procedimentos)
```

---

## 8. MONITORAMENTO

### Verificar Saúde dos Dados

```sql
-- Planejamentos orfãos (disciplina deletada)
SELECT COUNT(*) FROM procedures_planejamentotreinamento 
WHERE origem='MATRIZ' AND disciplina_id IS NULL;

-- Planejamentos com procedimento deletado
SELECT COUNT(*) FROM procedures_planejamentotreinamento 
WHERE procedimento_id IS NULL AND origem='LIVRE';

-- Associações inválidas
SELECT COUNT(*) FROM procedures_disciplinaprocedimento 
WHERE disciplina_id NOT IN (SELECT id FROM procedures_disciplina)
   OR procedimento_id NOT IN (SELECT id FROM procedures_procedimento);
```

---

**Referência Técnica Completa para Desenvolvimento**
