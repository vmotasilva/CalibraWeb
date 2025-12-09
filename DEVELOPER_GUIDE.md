# CALIBRAWEB - TEAM DOCUMENTATION & DEVELOPER GUIDE
## Complete guide for developers, maintainers, and DevOps engineers

---

## 📋 TABLE OF CONTENTS

1. [Getting Started](#getting-started)
2. [Project Architecture](#project-architecture)
3. [Development Workflow](#development-workflow)
4. [Adding New Features](#adding-new-features)
5. [Database Migrations](#database-migrations)
6. [Query Optimization](#query-optimization)
7. [Testing Guidelines](#testing-guidelines)
8. [Deployment Procedures](#deployment-procedures)
9. [Troubleshooting](#troubleshooting)
10. [Common Tasks](#common-tasks)

---

## GETTING STARTED

### 1. Environment Setup

**Required**:
- Python 3.11+
- PostgreSQL 12+ (production) or SQLite (development)
- Redis 6+ (optional for caching)
- Git

**Installation**:

```bash
# Clone repository
git clone https://github.com/vmotasilva/CalibraWeb.git
cd CalibraWeb

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Start development server
python manage.py runserver
```

**Access**:
- Django admin: http://localhost:8000/admin/
- API (if configured): http://localhost:8000/api/

### 2. Project Directory Structure

```
CalibraWeb/
├── config/                 # Django settings and WSGI/ASGI
│   ├── settings.py        # Main configuration
│   ├── urls.py            # URL routing
│   ├── wsgi.py            # Production WSGI
│   └── asgi.py            # Async support
│
├── core/                   # Core app (shared utilities)
├── organization/           # Organization structure (Setores, CentroCusto)
├── rh/                     # Human Resources (Colaboradores, Férias)
├── metrologia/             # Metrology (Instrumentos, Calibrações)
├── procurements/           # Procurement (Fornecedores, Orçamentos)
├── training/               # Training (Procedimentos, Registros)
├── documents/              # Document management
├── shared/                 # Shared utilities, models, decorators
│
├── static/                 # CSS, JavaScript, images
├── templates/              # HTML templates
├── backups/                # Database backups
│
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
│
└── docs/
    ├── DEPLOYMENT_CHECKLIST.md
    ├── DEPLOYMENT_VALIDATION_REPORT.md
    ├── REDIS_CACHING_STRATEGY.md
    ├── PHASE_12_PERFORMANCE_SUMMARY.md
    └── ...
```

---

## PROJECT ARCHITECTURE

### 8-App Modular Structure

**Organization App**: `organization/`
- Setor (Department/Sector)
- CentroCusto (Cost Center)
- HierarquiaSetor (Hierarchy)
- Responsável (Responsibility)

**HR App**: `rh/`
- Colaborador (Employee)
- Férias (Vacation)
- Ocorrência (Incident)
- DocumentoPessoal (Personal Document)

**Metrology App**: `metrologia/`
- Instrumento (Instrument)
- UnidadeMedida (Unit)
- FaixaMedicao (Measurement Range)
- HistoricoCalibracao (Calibration History)
- ResultadoFaixaCalibração (Measurement Result)
- SolicitacaoInstrumento (Instrument Request)
- OcorrenciaInstrumento (Instrument Incident)
- OrdemCalibração (Calibration Order)
- HistoricoManutencao (Maintenance History)

**Procurement App**: `procurements/`
- Fornecedor (Vendor)
- AvaliacaoFornecedor (Vendor Evaluation)
- ProcessoCotacao (Quotation Process)
- Orcamento (Budget)

**Training App**: `training/`
- Procedimento (Procedure)
- ProcedimentoRevisao (Procedure Revision)
- PacoteTreinamento (Training Package)
- RegistroTreinamento (Training Record)

**Other Apps**:
- `core/`: Shared functionality
- `documents/`: Document management
- `shared/`: Utilities and decorators
- `qms/`: Quality Management System

### Relationship Map

```
CentroCusto ──1──┬──N── Setor ──1──┬──N── Colaborador
                 │                 └──N── Responsável
                 │
                 └──N── Instrumento ──1──N── FaixaMedicao
                                   ├──1──N── HistoricoCalibracao
                                   └──1──N── Ocorrencia

HistoricoCalibracao ──1──N── ResultadoFaixaCalibração

Colaborador ────1──N── RegistroTreinamento ──1── PacoteTreinamento
                                             ├──N── Procedimento
                                             └──1── ProcedimentoRevisao

Fornecedor ──1──N── AvaliacaoFornecedor
        └──1──N── ProcessoCotacao ──1──N── Orcamento
```

---

## DEVELOPMENT WORKFLOW

### 1. Creating a Feature Branch

```bash
# Ensure main branch is up to date
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/your-feature-name
# or for bug fixes
git checkout -b fix/bug-description
```

### 2. Making Changes

**Models**:
```python
# In appropriate app/models.py
from django.db import models
from shared.models import BaseModel

class YourModel(BaseModel):
    """Your model description"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    
    class Meta:
        verbose_name = "Your Model"
        verbose_name_plural = "Your Models"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
```

**Views**:
```python
# In appropriate app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import YourModel

@login_required
def model_list(request):
    """Display list of models"""
    models = YourModel.objects.all()
    return render(request, 'app/model_list.html', {'models': models})
```

**Admin**:
```python
# In appropriate app/admin.py
from django.contrib import admin
from .models import YourModel

@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']
    
    # Add query optimization
    list_select_related = []  # For ForeignKey fields
    list_prefetch_related = []  # For ManyToMany and reverse ForeignKey
```

### 3. Database Migrations

```bash
# After model changes, create migration
python manage.py makemigrations [app_name]

# Review migration before running
cat [app]/migrations/0001_initial.py

# Apply migration to database
python manage.py migrate

# To rollback specific migration
python manage.py migrate [app] [migration_number]
```

### 4. Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test [app_name]

# Run with coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report

# Integration tests
pytest integration_tests.py -v
```

### 5. Committing Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Feature: Brief description of changes

- Detailed change 1
- Detailed change 2
- Related issue: #123"

# Push to remote
git push origin feature/your-feature-name
```

### 6. Creating Pull Request

1. Go to GitHub repository
2. Click "New Pull Request"
3. Select your branch
4. Add description following PR template
5. Request reviewers
6. Address feedback and update

---

## ADDING NEW FEATURES

### Step-by-Step: Adding a New Model

**1. Create the model** (`app/models.py`):
```python
class NewFeature(BaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField()
    related_model = models.ForeignKey(RelatedModel, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name
```

**2. Create admin interface** (`app/admin.py`):
```python
@admin.register(NewFeature)
class NewFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    list_select_related = ['related_model']
    search_fields = ['name']
```

**3. Create migration**:
```bash
python manage.py makemigrations
python manage.py migrate
```

**4. Create views** (if needed) (`app/views.py`):
```python
def new_feature_list(request):
    features = NewFeature.objects.all()
    return render(request, 'app/new_feature_list.html', {'features': features})
```

**5. Create templates** (if needed):
```html
<!-- templates/app/new_feature_list.html -->
{% extends "base.html" %}

{% block content %}
<h1>Features</h1>
<table>
    {% for feature in features %}
    <tr>
        <td>{{ feature.name }}</td>
        <td>{{ feature.description }}</td>
    </tr>
    {% endfor %}
</table>
{% endblock %}
```

**6. Add to URLs** (`app/urls.py`):
```python
from django.urls import path
from . import views

urlpatterns = [
    path('features/', views.new_feature_list, name='new_feature_list'),
]
```

**7. Test thoroughly**:
```bash
python manage.py test [app_name].tests.TestNewFeature
```

---

## QUERY OPTIMIZATION

### Best Practices

**1. Use select_related for ForeignKey**:
```python
# ❌ BAD: N+1 query problem
users = User.objects.all()
for user in users:
    print(user.department.name)  # Extra query per user

# ✅ GOOD: Single query
users = User.objects.select_related('department')
for user in users:
    print(user.department.name)  # Already loaded
```

**2. Use prefetch_related for ManyToMany/Reverse FK**:
```python
# ❌ BAD: Extra query per object
departments = Department.objects.all()
for dept in departments:
    print(dept.employees.all())  # Extra query

# ✅ GOOD: Two queries (one for dept, one for all employees)
departments = Department.objects.prefetch_related('employees')
```

**3. Use only/defer for large fields**:
```python
# ❌ BAD: Load all fields including large text
users = User.objects.all()

# ✅ GOOD: Load only needed fields
users = User.objects.only('id', 'name', 'email')

# Or defer large fields
users = User.objects.defer('biography', 'profile_image')
```

**4. Use annotate/aggregate for aggregations**:
```python
from django.db.models import Count, Sum, Avg

# ❌ BAD: Load all and count in Python
departments = Department.objects.all()
employee_count = sum(len(d.employees.all()) for d in departments)

# ✅ GOOD: Count at database level
from django.db.models import Count
departments = Department.objects.annotate(
    employee_count=Count('employees')
)
total = sum(d.employee_count for d in departments)
```

**5. Use filter with Q objects for complex queries**:
```python
from django.db.models import Q

# ✅ GOOD: Complex filtering at database level
users = User.objects.filter(
    Q(department=dept) | Q(manager=manager)
) & Q(active=True)
```

### Admin Optimization Template

```python
@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    # For ForeignKey/OneToOne relationships
    list_select_related = ['department', 'manager']
    
    # For ManyToMany/Reverse ForeignKey
    list_prefetch_related = ['projects', 'roles']
    
    # Limit displayed fields
    list_display = ['name', 'department', 'email']
    
    # Search on indexed fields only
    search_fields = ['name', 'email']
    
    # Filter efficiently
    list_filter = ['active', 'created_at']
    
    # Pagination
    list_per_page = 50
```

---

## TESTING GUIDELINES

### Unit Tests

```python
# app/tests.py
from django.test import TestCase
from .models import YourModel

class YourModelTests(TestCase):
    def setUp(self):
        """Set up test data"""
        self.model = YourModel.objects.create(name="Test")
    
    def test_model_creation(self):
        """Test model can be created"""
        self.assertEqual(self.model.name, "Test")
    
    def test_model_str(self):
        """Test __str__ method"""
        self.assertEqual(str(self.model), "Test")
```

### Admin Tests

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User

class AdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'admin@test.com', 'admin')
        self.client.login(username='admin', password='admin')
    
    def test_admin_access(self):
        response = self.client.get('/admin/app/yourmodel/')
        self.assertEqual(response.status_code, 200)
```

### Integration Tests

```bash
# Run integration tests
pytest integration_tests.py -v

# Run with coverage
pytest --cov=. integration_tests.py
```

---

## DEPLOYMENT PROCEDURES

### Pre-Deployment Checklist

```bash
# 1. Run validation
python test_production_env.py
python security_audit.py

# 2. Run tests
python manage.py test
pytest integration_tests.py

# 3. Check for issues
python manage.py check
python manage.py check --deploy

# 4. Backup database
python backup_manager.py backup

# 5. Collect static files
python manage.py collectstatic --noinput
```

### Deployment Steps

**Option 1: Manual VPS Deployment**

```bash
# SSH into server
ssh user@server

# Pull latest code
cd /path/to/calibraweb
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart application
systemctl restart calibraweb
systemctl restart gunicorn-calibraweb
systemctl restart nginx
```

**Option 2: Railway Deployment**

```bash
# Just push to git!
git push origin main  # Automatically deploys
```

**Option 3: Docker Deployment**

```bash
# Build image
docker build -t calibraweb:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -e SECRET_KEY=<key> \
  -e DEBUG=False \
  calibraweb:latest

# Or with docker-compose
docker-compose up -d
```

---

## TROUBLESHOOTING

### Common Issues

**1. ModuleNotFoundError**

```python
# Error: No module named 'shared'
# Solution: Ensure PYTHONPATH includes project root

# In manage.py or settings:
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

**2. Database Connection Error**

```python
# Error: could not connect to server
# Solution: Check DATABASE_URL environment variable

# Test connection:
python manage.py dbshell
```

**3. Static Files Not Loading**

```bash
# Error: 404 for static files
# Solution: Collect static files

python manage.py collectstatic --noinput

# Check settings.py:
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

**4. Migration Conflicts**

```bash
# Error: conflicting migrations
# Solution:

# Show migration history
python manage.py showmigrations

# Rollback to specific migration
python manage.py migrate [app] [migration_number]

# Delete conflicting migration files and recreate
rm [app]/migrations/0XXX_*.py
python manage.py makemigrations
```

### Debug Mode

```python
# Temporarily enable debug for troubleshooting
# In settings.py or manage.py
import os
os.environ['DEBUG'] = 'True'

# Or via .env
DEBUG=True
```

### View Logs

```bash
# Django logs
tail -f /var/log/django.log

# Gunicorn logs
tail -f /var/log/gunicorn.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

---

## COMMON TASKS

### 1. Reset Database (Development Only)

```bash
# Warning: Deletes all data!
python manage.py flush

# Or remove and recreate
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### 2. Backup and Restore Database

```bash
# PostgreSQL
pg_dump dbname > backup.sql
psql dbname < backup.sql

# Using backup_manager.py
python backup_manager.py backup
python backup_manager.py restore backup_file_name.sql
```

### 3. Clear Cache

```bash
# Django cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()

# Or via cache manager
python -c "from django.core.cache import cache; cache.clear()"
```

### 4. Create Admin User

```bash
python manage.py createsuperuser

# Or in shell
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.create_superuser('username', 'email@example.com', 'password')
```

### 5. Export/Import Data

```bash
# Export data
python manage.py dumpdata app_name > data_backup.json

# Import data
python manage.py loaddata data_backup.json
```

### 6. Run Custom Management Command

```bash
# Create new command
mkdir -p [app]/management/commands
touch [app]/management/__init__.py
touch [app]/management/commands/__init__.py
touch [app]/management/commands/my_command.py

# In my_command.py:
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'My custom command'
    
    def handle(self, *args, **options):
        self.stdout.write('Hello World')

# Run command
python manage.py my_command
```

---

## SUPPORT & RESOURCES

**Documentation Files**:
- `DEPLOYMENT_CHECKLIST.md` - Deployment guide
- `PHASE_12_PERFORMANCE_SUMMARY.md` - Performance optimization
- `REDIS_CACHING_STRATEGY.md` - Caching implementation
- `PROJETO_ARQUITETURA.md` - Architecture overview

**External Resources**:
- [Django Documentation](https://docs.djangoproject.com/)
- [Django Best Practices](https://docs.djangoproject.com/en/5.0/faq/usage/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Git Workflow Guide](https://guides.github.com/introduction/flow/)

**Getting Help**:
- Check TROUBLESHOOTING.md
- Review similar models in codebase
- Search GitHub issues
- Ask in development channel

---

**Document Version**: 1.0  
**Last Updated**: December 8, 2025  
**Maintainer**: CalibraWeb Development Team
