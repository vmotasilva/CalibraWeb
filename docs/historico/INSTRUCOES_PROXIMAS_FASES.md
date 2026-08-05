# Instruções para Continuação da Reorganização

## 📌 Status Atual

✅ **Fase 1 Concluída**: Estrutura de diretórios e modelos base criados

- [x] Criada estrutura de 8 módulos especializados
- [x] Modelos divididos por domínio de negócio
- [x] Imports base configurados
- [x] Arquivos de documentação criados

---

## 🔄 Próximas Fases

### **Fase 2: Criar apps.py para cada módulo**

Exemplo para `core/apps.py`:
```python
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core - Base do Sistema'
```

Repita para: `organization`, `rh`, `metrologia`, `training`, `procurements`, `documents`

### **Fase 3: Atualizar settings.py**

Adicione ao `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Novos módulos
    'core.apps.CoreConfig',
    'organization.apps.OrganizationConfig',
    'rh.apps.RhConfig',
    'metrologia.apps.MetrologiaConfig',
    'training.apps.TrainingConfig',
    'procurements.apps.ProcurementsConfig',
    'documents.apps.DocumentsConfig',
    'shared',
    
    # Apps antigas (manter por enquanto para compatibilidade)
    'qms',
    'widget_tweaks',
]
```

### **Fase 4: Migrar views.py**

O arquivo original `qms/views.py` (2.584 linhas) deve ser dividido:

**metrologia/views/crud.py** - CRUD de instrumentos
```python
@login_required
def novo_instrumento_view(request):
    # Lógica de novo instrumento
    pass
```

**metrologia/views/calibracao.py** - Calibração
```python
@login_required
def registrar_historico_calibracao_view(request):
    # Lógica de calibração
    pass
```

E assim por diante para cada funcionalidade...

### **Fase 5: Migrar forms.py**

Dividir `qms/forms.py` em:
- `metrologia/forms/instrumento.py`
- `metrologia/forms/calibracao.py`
- `rh/forms/colaborador.py`
- `training/forms/procedimento.py`
- etc.

### **Fase 6: Migrar tasks.py**

Dividir `qms/tasks.py` em:
- `metrologia/tasks/import_instrumentos.py`
- `rh/tasks/import_colaboradores.py`
- `training/tasks/import_procedimentos.py`
- etc.

### **Fase 7: Reorganizar templates**

Estruturar como:
```
qms/templates/
├── base.html
├── 404.html
├── 500.html
└── registration/
    └── login.html

metrologia/templates/metrologia/
├── list.html
├── detail.html
├── forms/
│   └── instrumento_form.html
└── calibracao/
    └── historico.html

rh/templates/rh/
├── list.html
├── detail.html
└── forms/

training/templates/training/
├── procedimentos/
├── treinamentos/
└── forms/
```

### **Fase 8: Reorganizar static files**

```
qms/static/
├── css/
│   └── global.css
└── js/
    └── global.js

metrologia/static/metrologia/
├── css/
│   └── metrologia.css
└── js/
    ├── instrumento.js
    └── calibracao.js

rh/static/rh/
├── css/
│   └── rh.css
└── js/
    └── colaborador.js
```

### **Fase 9: Atualizar URLs**

Criar `urls.py` em cada módulo:

**metrologia/urls.py**:
```python
from django.urls import path
from . import views

app_name = 'metrologia'

urlpatterns = [
    path('', views.metrologia_dashboard_view, name='dashboard'),
    path('novo/', views.novo_instrumento_view, name='novo_instrumento'),
    path('<int:instrumento_id>/', views.detalhe_instrumento_view, name='detalhe_instrumento'),
    # ... mais rotas
]
```

**config/urls.py** (atualizar):
```python
from django.urls import path, include
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(...), name='login'),
    
    # Incluir URLs de cada módulo
    path('metrologia/', include('metrologia.urls')),
    path('rh/', include('rh.urls')),
    path('training/', include('training.urls')),
    path('procurements/', include('procurements.urls')),
    path('documents/', include('documents.urls')),
    
    # QMS (dashboard e admin customizado)
    path('', views.dashboard_view, name='home'),
]
```

### **Fase 10: Executar migrações**

```bash
python manage.py makemigrations
python manage.py migrate
```

### **Fase 11: Testes**

1. Testar cada módulo isoladamente
2. Testar integrações entre módulos
3. Testar URLs e views
4. Testar formulários e validações
5. Testar tarefas assíncronas (Celery)

---

## 🛠️ Checklist de Implementação

### Antes de começar cada fase:
- [ ] Criar branch de trabalho
- [ ] Backup dos arquivos originais
- [ ] Documentar mudanças

### Durante cada fase:
- [ ] Implementar funcionalidade
- [ ] Testar manualmente
- [ ] Atualizar imports
- [ ] Documentar mudanças

### Depois de cada fase:
- [ ] Executar testes
- [ ] Revisar código
- [ ] Fazer commit

---

## 🚀 Dica de Aceleração

Para acelerar o processo:

1. **Use search/replace** nos IDEs para atualizar imports em batch
2. **Automatize** a criação de arquivos base (apps.py, __init__.py)
3. **Teste durante o processo**, não no final
4. **Mantenha um git log** de cada fase

---

## 📞 Suporte

Se encontrar problemas:

1. Verifique se todos os imports estão corretos
2. Confirme que `INSTALLED_APPS` foi atualizado
3. Execute `python manage.py check` para validar
4. Consulte a documentação do Django sobre app configs

---

## 🎯 Próximo Passo

Comece pela **Fase 2**: Criar `apps.py` para cada módulo.

Exemplo rápido:
```bash
# Criar apps.py para cada módulo
for app in core organization rh metrologia training procurements documents; do
    cat > "$app/apps.py" << 'EOF'
from django.apps import AppConfig

class $(capitalize)Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '$(app)'
EOF
done
```

---

**Tempo estimado total**: 15-20 horas (pelas estimativas iniciais)

**Estágio atual**: 1/10 (10% concluído)

