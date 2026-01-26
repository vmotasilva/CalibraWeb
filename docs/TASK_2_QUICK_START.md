# Task 2 Quick Start: Preparar Estrutura de Apps

**Status:** 🔴 PRONTO PARA COMEÇAR  
**Duração Estimada:** 2-3 horas  
**Dependências:** Task 1 ✅ (COMPLETA)

---

## 📋 Checklist de Execução Rápida

### Step 1: Criar Estrutura Base (15 mins)
Você vai criar arquivos `models.py` vazios em cada app que não o tem:

**Apps que precisam de models.py:**
```
organization/models.py       ← CREATE
rh/models.py                 ← CREATE
metrologia/models.py         ← CREATE
procurements/models.py       ← CREATE
training/models.py           ← CREATE
core/models.py               ← UPDATE (adicionar constantes + UnidadeMedida)
```

**Comando para criar:**
```bash
# Navegar para raiz do projeto
cd c:\CalibraWeb

# Criar arquivos vazios
New-Item -Path organization/models.py -ItemType File -Force
New-Item -Path rh/models.py -ItemType File -Force
New-Item -Path metrologia/models.py -ItemType File -Force
New-Item -Path procurements/models.py -ItemType File -Force
New-Item -Path training/models.py -ItemType File -Force
```

### Step 2: Adicionar Imports Padrão (10 mins)
Cada arquivo precisa de imports básicos. Use o template abaixo:

**Template para models.py:**
```python
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
import uuid

# App-specific imports will go here
```

### Step 3: Copiar Constantes para CORE (5 mins)

**core/models.py deve conter:**
```python
from django.db import models

# ==============================================================================
# CONSTANTES E OPÇÕES GERAIS
# ==============================================================================
STATUS_CHOICES = [("ATIVO", "Ativo"), ("INATIVO", "Inativo"), ("INSS", "Afastado INSS")]
TURNOS_CHOICES = [
    ("ADM", "Administrativo"),
    ("TURNO_1", "Turno 1"),
    ("TURNO_2", "Turno 2"),
    ("TURNO_3", "Turno 3"),
    ("12X36", "12x36"),
]

# MODELO: UnidadeMedida (copy from qms/models.py lines 305-314)
class UnidadeMedida(models.Model):
    nome = models.CharField(max_length=50, unique=True, verbose_name="Unidade de Medida")
    descricao = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["nome"]
```

### Step 4: Validar Estrutura (5 mins)

```bash
python manage.py check
# Deve mostrar: System check identified no issues (0 silenced).

python manage.py test qms.tests.OcorrenciaTests.test_ocorrencia_creation --verbosity=0
# Deve passar (confirma que DB ainda funciona)
```

---

## 🎯 Próximas Ações (ORDEM CRÍTICA)

1. ✅ **Task 1 Completa** - Análise de dependências feita
2. 🔴 **Task 2 Começar AGORA** - Preparar estrutura (você está aqui)
3. ⏳ **Task 3** - Mover modelos de qms para apps corretos
4. ⏳ **Task 4** - Corrigir imports em views/forms
5. ⏳ **Task 5** - Criar migrations Django
6. ⏳ **Task 6** - Testar tudo (30+ testes devem passar)

---

## 📖 Recursos de Referência

- **EXECUTION_ROADMAP_DETAILED.md** - Instruções completas de Task 2
- **TASK_1_ANALYSIS_REPORT.md** - Resultado da análise de dependências
- **qms/models.py** - Arquivo fonte com todos os 27 modelos (linhas 1-997)

---

## ⚠️ Pontos Críticos

### ❌ NÃO FAÇA:
- ❌ Mover modelos antes de criar estrutura (Task 2)
- ❌ Deletar qms/models.py original
- ❌ Adicionar modelos fora da ordem de dependências
- ❌ Usar imports circulares (sempre usar string references)

### ✅ FAÇA:
- ✅ Seguir ordem: CORE → ORGANIZATION → RH → METROLOGIA → PROCUREMENTS → TRAINING → QMS
- ✅ Usar string references: `models.ForeignKey('rh.Colaborador', ...)`
- ✅ Testar com `python manage.py check` após cada passo
- ✅ Fazer commits frequentes no git

---

## 📝 Template Completo para models.py

Use este template como base para cada arquivo:

```python
from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
import uuid

# ==============================================================================
# [APP_NAME] - MODELOS
# ==============================================================================

# Imports locais (se houver):
# from other_app.models import SomeModel

# Imports cross-app (use string references nos ForeignKey!):
# class MyModel(models.Model):
#     reference = models.ForeignKey('other_app.Model', on_delete=models.CASCADE)


# Adicione os modelos aqui
# (copiar exatamente de qms/models.py)

```

---

## 🔔 Próximo Passo Específico

**Assim que concluir Task 2:**

1. Commit das mudanças:
   ```bash
   git add -A
   git commit -m "Task 2: Create app structure with models.py files"
   ```

2. Executar validação:
   ```bash
   python manage.py check
   python manage.py test qms.tests --verbosity=0
   ```

3. Iniciar Task 3 (mover modelos)

---

**Pronto para começar? Task 2 leva ~2-3 horas. Siga as instruções em EXECUTION_ROADMAP_DETAILED.md para o detail completo.**

