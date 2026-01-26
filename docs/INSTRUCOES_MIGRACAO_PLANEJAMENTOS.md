# Instruções para Migração de Planejamentos

## Mudanças Realizadas

Foi alterado o modelo `PlanejamentoTreinamento` para suportar **múltiplos procedimentos** por planejamento:

**Antes:**
```python
procedimento = models.ForeignKey(Procedimento, ...)  # 1 procedimento
```

**Depois:**
```python
procedimentos = models.ManyToManyField(Procedimento, ...)  # N procedimentos
```

## Passos para Aplicar a Migração

### 1. Fazer backup do banco de dados
```bash
python manage.py dumpdata procedures.PlanejamentoTreinamento > backup_planejamentos.json
```

### 2. Executar os comandos SQL manualmente no banco

```sql
-- 1. Criar nova tabela ManyToMany
CREATE TABLE procedures_planejamentotreinamento_procedimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planejamentotreinamento_id INTEGER NOT NULL,
    procedimento_id INTEGER NOT NULL,
    FOREIGN KEY (planejamentotreinamento_id) REFERENCES procedures_planejamentotreinamento(id),
    FOREIGN KEY (procedimento_id) REFERENCES procedures_procedimento(id),
    UNIQUE (planejamentotreinamento_id, procedimento_id)
);

-- 2. Migrar dados existentes (copiar procedimento único para procedimentos múltiplos)
INSERT INTO procedures_planejamentotreinamento_procedimentos 
    (planejamentotreinamento_id, procedimento_id)
SELECT id, procedimento_id 
FROM procedures_planejamentotreinamento 
WHERE procedimento_id IS NOT NULL;

-- 3. (OPCIONAL) Remover coluna antiga após confirmar que tudo funciona
-- ALTER TABLE procedures_planejamentotreinamento DROP COLUMN procedimento_id;
```

### 3. Ou usar script Python para migração

Criar arquivo `migrate_planejamentos.py`:

```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibra.settings')
django.setup()

from procedures.models import PlanejamentoTreinamento

# Para cada planejamento que tinha procedimento único
count = 0
for planj in PlanejamentoTreinamento.objects.all():
    # Se usar old field, adicionar ao novo many-to-many
    if hasattr(planj, '_procedimento_antigo_id'):
        planj.procedimentos.add(planj._procedimento_antigo_id)
        count += 1
        
print(f"Migrados {count} planejamentos")
```

## Benefícios da Mudança

✅ **Sem duplicação**: Um planejamento com 5 procedimentos = 1 registro
❌ **Antes**: Um planejamento com 5 procedimentos = 5 registros duplicados

✅ **Mais flexível**: Adicionar/remover procedimentos sem recriar planejamento
✅ **Melhor UX**: Lista de planejamentos mais limpa
✅ **Relação correta**: 1 planejamento → N procedimentos + N colaboradores
