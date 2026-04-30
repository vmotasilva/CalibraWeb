# Relação 1 para N - Padrões de Calibração

## Estrutura Implementada

### Modelos
```
HistoricoCalibracao (1)
    └── padroes_arquivo (related_name)
            ├── ArquivoPadrao (N)
            ├── ArquivoPadrao (N)
            └── ArquivoPadrao (N)
```

### Banco de Dados

#### Tabela: metrologia_historicocalibracao
```
id | instrumento_id | data_calibracao | ... | certificado
```

#### Tabela: metrologia_arquivopadrao
```
id | historico_id (FK) | nome | descricao | arquivo | data_upload
```

**Relação:** Cada `HistoricoCalibracao` pode ter múltiplos `ArquivoPadrao`

---

## Como Funciona

### 1. Criar Histórico
```python
historico = HistoricoCalibracao.objects.create(
    instrumento=instrumento,
    data_calibracao=date.today(),
    # ... outros campos
)
```

### 2. Adicionar Múltiplos Padrões
```python
ArquivoPadrao.objects.create(
    historico=historico,  # FK para histórico
    nome="Padrão 1",
    arquivo=file1
)

ArquivoPadrao.objects.create(
    historico=historico,  # Mesmo histórico
    nome="Padrão 2",
    arquivo=file2
)
```

### 3. Consultar Padrões do Histórico
```python
# Acessar todos os padrões de um histórico
padroes = historico.padroes_arquivo.all()

# Contar padrões
count = historico.padroes_arquivo.count()

# Filtrar padrões
pdf_pequenos = historico.padroes_arquivo.filter(arquivo__size__lt=1000000)
```

---

## Fluxo na Interface

1. **Editar Histórico** → Tela de edição
2. **Selecionar Múltiplos PDFs** → Input `type="file"` com `multiple`
3. **Clicar "Anexar Padrões"** → POST para `update_history`
4. **View processa cada arquivo:**
   - Valida PDF
   - Cria `ArquivoPadrao` com `historico_id`
   - Salva arquivo no storage
5. **Template exibe:** `historico.padroes_arquivo.all`

---

## Query Optimization

### Prefetch para Performance
```python
historicos = HistoricoCalibracao.objects\
    .select_related('instrumento')\
    .prefetch_related('padroes_arquivo')\
    .all()
```

### Acesso sem N+1 Queries
```python
for historico in historicos:
    for padrao in historico.padroes_arquivo.all():  # Não faz query adicional
        print(padrao.nome)
```

---

## Remoção de Padrão

### Antes (ManyToMany)
```python
historico.arquivos_padroes.remove(padrao)
padrao.delete()
```

### Depois (ForeignKey)
```python
padrao.delete()  # Cascata automática
```

---

## Vantagens da Nova Estrutura

✅ **Relação 1:N clara** - Um histórico, múltiplos padrões  
✅ **Integridade referencial** - FK garante histórico sempre existe  
✅ **Queries mais eficientes** - Sem join table M2M  
✅ **Fácil filtragem** - `padroes_arquivo.filter(...)`  
✅ **Cascata automática** - Deletar histórico remove padrões  
✅ **Melhor para admin** - FK inline no Django admin

---

## Migrações

```bash
# Criar migração
python manage.py makemigrations metrologia --name "refactor_arquivo_padrao_model"

# Aplicar migração
python manage.py migrate
```

---

## Exemplo Completo

```python
from metrologia.models import Instrumento, HistoricoCalibracao, ArquivoPadrao
from datetime import date

# 1. Obter instrumento
instrumento = Instrumento.objects.get(tag='CP-01')

# 2. Criar histórico
historico = HistoricoCalibracao.objects.create(
    instrumento=instrumento,
    data_calibracao=date.today(),
    tipo_calibracao='EXTERNA',
)

# 3. Adicionar múltiplos padrões
padroes_nomes = ['Padrão_1.pdf', 'Padrão_2.pdf', 'Padrão_3.pdf']
for nome in padroes_nomes:
    ArquivoPadrao.objects.create(
        historico=historico,
        nome=nome,
        arquivo=open(f'/path/{nome}', 'rb')
    )

# 4. Acessar padrões
for padrao in historico.padroes_arquivo.all():
    print(f"{padrao.nome}: {padrao.arquivo.url}")
```
