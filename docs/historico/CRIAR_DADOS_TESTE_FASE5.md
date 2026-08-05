# 🧪 CRIAR DADOS DE TESTE PARA FASE 5

## 📋 Visão Geral

Para testar as funcionalidades de exportação (Excel, CSV, PDF) e tarefas agendadas, você precisa ter dados no banco. Este guia mostra como criar dados de teste automaticamente.

---

## 🚀 Usar Script de Fixtures

### Opção 1: Via Django Shell (Recomendado)

```bash
# Terminal
cd c:\CalibraWeb
python manage.py shell < scripts/create_test_data_fase5.py
```

Saída esperada:
```
================================================================================
CREATING TEST DATA FOR PHASE 5 - EXPORTS AND REPORTS
================================================================================

[1/5] Creating instrument categories...
  ✓ Criada categoria: Paquímetro
  ✓ Criada categoria: Termômetro
  ✓ Criada categoria: Manômetro
  ✓ Criada categoria: Multímetro
  ✓ Criada categoria: Escala

[2/5] Creating sectors...
  ✓ Criado setor: Metrologia
  ✓ Criado setor: TI
  ✓ Criado setor: Produção

[3/5] Creating test instruments...
  ✓ Instrumento criado: PAQ-001 [VIGENTE]
  ✓ Instrumento criado: PAQ-002 [VENCIDO -30d]
  ...

[4/5] Creating calibration histories...
  ✓ Criados 40 registros de calibração

================================================================================
TEST DATA CREATED SUCCESSFULLY!
================================================================================

  Categorias: 5
  Setores: 3
  Instrumentos: 20
  Históricos de Calibração: 40

📊 Test Data Statistics:
  • Instrumentos vencidos: 6
  • Vencendo em 30 dias: 8
  • Vigentes: 6

✅ Dados prontos para testes de export!
================================================================================
```

### Opção 2: Dentro do Django Shell

```bash
python manage.py shell

# Copiar e colar o conteúdo de scripts/create_test_data_fase5.py
```

---

## 📊 O Que é Criado

### Categorias (5)
```
1. Paquímetro
2. Termômetro
3. Manômetro
4. Multímetro
5. Escala
```

### Setores (3)
```
1. Metrologia
2. TI
3. Produção
```

### Instrumentos (20)
Distribuídos entre categorias e setores:
- 6 instrumentos **VENCIDOS** (calibração já passou)
- 8 instrumentos **VENCENDO EM 30 DIAS** (urgentes)
- 6 instrumentos **VIGENTES** (com tempo)

Exemplos:
```
PAQ-001: Paquímetro Digital 0-150mm (Vigente)
PAQ-002: Paquímetro Analógico 0-200mm (Vencido há 30 dias)
TERM-001: Termômetro Digital (Vence em 15 dias)
```

### Calibração Histórica (40)
Cada instrumento tem 2 registros de calibração:
- Data de calibração (passada)
- Data da próxima calibração
- Resultado, certificado, fornecedor, etc.

---

## ✅ Testar Exports com Dados

Após rodar o script, você pode testar:

### 1. Exportar Instrumentos

```
1. Dashboard → Metrologia → Instrumentos
2. Clicar "Exportar" → Excel
3. Deve baixar arquivo com 20 instrumentos
```

### 2. Exportar com Filtro

```
1. Dashboard → Metrologia → Instrumentos
2. Filtro: Status = Vencido
3. Clicar "Exportar" → Excel
4. Deve ter apenas 6 instrumentos
```

### 3. Exportar Estatísticas

```
1. Dashboard → Metrologia → Estatísticas
2. Clicar "Exportar" → Excel
3. Deve ver KPIs, por categoria, por setor
```

### 4. Relatório de Vencidos

```
1. Dashboard → Metrologia → Vencidos
2. Clicar "Exportar" → Excel
3. Deve ver 6 instrumentos vencidos
```

---

## 🔧 Customizar Dados

Se quiser criar dados diferentes, editar `scripts/create_test_data_fase5.py`:

### Adicionar Mais Instrumentos

```python
instruments_data = [
    ("PAQ-001", "Paquímetro Digital", 0),  # dias até vencer
    ("TERMO-001", "Termômetro", -30),  # negativo = vencido
    # Adicionar mais...
]
```

### Adicionar Mais Categorias

```python
categories = [
    ("Paquímetro", "Descrição"),
    ("Termômetro", "Descrição"),
    # Adicionar mais...
]
```

### Mudar Proporção Vencido/Vigente

Modificar o `dias_diff` na lista `instruments_data`:
```python
("CODIGO", "Descrição", dias_diff)
#                       ^^^^^^^^
# Positivo: vence em X dias
# Negativo: vencido há X dias
# 0: vence hoje
```

---

## 🧹 Limpar Dados (Se Necessário)

Se precisar remover os dados de teste:

```bash
python manage.py shell

>>> from metrologia.models import Instrumento, CategoriaInstrumento, HistoricoCalibracao
>>> from organization.models import Setor

# Deletar instrumentos
>>> Instrumento.objects.filter(codigo__startswith=('PAQ', 'TERM', 'MAN', 'MULTI', 'ESCA')).delete()

# Deletar históricos
>>> HistoricoCalibracao.objects.all().delete()

# Deletar categorias de teste
>>> CategoriaInstrumento.objects.filter(nome__in=['Paquímetro', 'Termômetro']).delete()

# Deletar setores de teste
>>> Setor.objects.filter(nome__in=['Metrologia', 'TI', 'Produção']).delete()

>>> print("✅ Dados deletados")
```

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'metrologia'"

**Solução:** Verificar que está no diretório correto
```bash
pwd  # Deve ser c:\CalibraWeb
python manage.py shell
```

### "OperationalError: no such table"

**Solução:** Rodar migrações primeiro
```bash
python manage.py migrate
# Depois rodar o script
```

### "Script rodou mas sem dados"

**Verificação:**
```bash
python manage.py shell
>>> from metrologia.models import Instrumento
>>> Instrumento.objects.count()  # Deve ser >= 20
```

Se for 0, verificar se há erros no script.

---

## 📊 Validar Dados

Após criar, validar no Django Admin:

```bash
# Criar superuser se não tiver
python manage.py createsuperuser

# Rodar servidor
python manage.py runserver

# Acessar http://localhost:8000/admin
# Login com superuser
# Verificar: Metrologia → Instrumentos (deve ter 20)
```

---

## 🧮 Estatísticas Esperadas

Após criar dados:

```
Instrumentos Ativos:        20
Históricos de Calibração:   40
Categorias:                  5
Setores:                     3

Status:
  - Vigentes:               ~6
  - Vencendo em 30d:        ~8
  - Vencidos:               ~6
```

---

## 🎯 Próximos Passos

Após criar dados de teste:

1. **Testar Exports**
   - Exportar cada formato (Excel, CSV, PDF)
   - Verificar se dados estão corretos
   - Verificar formatação

2. **Testar Filters**
   - Filtrar por status, setor, categoria
   - Exportar dados filtrados
   - Verificar se filtro foi aplicado

3. **Testar Tasks**
   ```bash
   celery -A config worker -l info
   celery -A config call qms.tasks.gerar_relatorio_diario_vencidos
   ```

4. **Testar Email**
   - Configurar email backend
   - Rodar tarefa e verificar inbox

---

## 💾 Backup dos Dados

Se criou dados bons para teste, fazer backup:

```bash
# Exportar dados
python manage.py dumpdata metrologia > metrologia_data.json
python manage.py dumpdata organization > organization_data.json

# Para restaurar depois
python manage.py loaddata metrologia_data.json organization_data.json
```

---

**Status: Pronto para testar! 🧪**
