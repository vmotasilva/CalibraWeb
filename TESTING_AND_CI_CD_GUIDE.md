# CalibraWeb - Testing & CI/CD Guide

**Created:** December 8, 2025  
**Status:** Testing Framework Established

---

## 📋 Overview

This guide covers the comprehensive testing and CI/CD infrastructure set up for the CalibraWeb project after the architectural refactoring. The system includes:

- **Unit Tests** - Django TestCase for models, views, forms
- **Integration Tests** - Full request/response testing  
- **Code Quality** - Black, isort, flake8
- **Security Scanning** - Bandit, safety
- **CI/CD Pipeline** - GitHub Actions workflows
- **Pre-commit Hooks** - Automated checks before commits
- **Coverage Reporting** - pytest-cov with 70% threshold

---

## 🧪 Running Tests

### Django's Built-in Test Runner

```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test metrologia

# Run with verbose output
python manage.py test --verbosity=2

# Keep test database
python manage.py test --keepdb

# Run specific test class
python manage.py test metrologia.tests.InstrumentoTests

# Run specific test method
python manage.py test metrologia.tests.InstrumentoTests.test_instrumento_creation
```

### Pytest with Coverage

```bash
# Run all tests with coverage
pytest --cov --cov-report=html --cov-report=term

# Run tests for specific module
pytest metrologia/

# Run with markers
pytest -m "not slow"  # Skip slow tests
pytest -m "models"    # Only run model tests
pytest -m "views"     # Only run view tests

# Run with verbose output
pytest -vv

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Run specific test
pytest metrologia/tests.py::InstrumentoTests::test_instrumento_creation
```

### Test Markers Available

```python
@pytest.mark.slow              # Slow tests
@pytest.mark.integration       # Integration tests
@pytest.mark.unit              # Unit tests
@pytest.mark.models            # Model tests
@pytest.mark.views             # View tests
@pytest.mark.forms             # Form tests
@pytest.mark.authentication    # Auth-required tests
```

---

## 📝 Test Structure

### Test Files Location

Each module has a `tests.py` file:

```
metrologia/
├── tests.py              # Unit and integration tests
├── models/models.py
├── views/views.py
└── forms/forms.py
```

### Test Classes by Type

```python
# Model tests
class CategoriaInstrumentoTests(TestCase):
    def test_categoria_instrument_creation(self):
        ...

# View tests  
class MetrologiaViewsTests(TestCase):
    def test_modulo_metrologia_view_authenticated(self):
        ...

# Import tests
class MetrologiaImportsTests(TestCase):
    def test_metrologia_models_import(self):
        ...
```

### Using Fixtures (pytest)

```python
@pytest.mark.django_db
def test_with_fixtures(colaborador, setor):
    assert colaborador.setor == setor

# Available fixtures in conftest.py:
# - client: Django test client
# - user: Test user
# - authenticated_client: Logged-in client
# - setor: Test Setor
# - colaborador: Test Colaborador
```

---

## 🔍 Code Quality Tools

### Black - Code Formatting

```bash
# Check formatting
black --check .

# Auto-format code
black .

# Format specific file
black metrologia/models/models.py
```

### isort - Import Sorting

```bash
# Check import ordering
isort --check-only .

# Fix import ordering
isort .

# Check specific file
isort --check-only metrologia/
```

### Flake8 - Linting

```bash
# Run flake8
flake8 .

# Check specific file
flake8 metrologia/views/views.py

# Ignore specific codes
flake8 --ignore=E501 .  # Ignore line too long
```

---

## 🔒 Security Scanning

### Bandit - Security Issues

```bash
# Run security scan
bandit -r .

# Generate JSON report
bandit -r . -f json -o bandit-report.json

# Exclude test files
bandit -r . --exclude tests.py
```

### Safety - Dependency Vulnerabilities

```bash
# Check for known vulnerabilities
safety check

# Generate JSON report
safety check --json
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline runs automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`

**Workflow File:** `.github/workflows/ci-cd.yml`

### Pipeline Jobs

1. **Test Job**
   - Python versions: 3.10, 3.11, 3.12
   - PostgreSQL service
   - Django system check
   - Database migrations
   - Django tests
   - Pytest with coverage
   - Coverage upload to Codecov

2. **Security Job**
   - Bandit security scan
   - Safety vulnerability check

3. **Deploy Job** (on main push only)
   - Deploys to production
   - Configure with your hosting platform

### Viewing Pipeline Results

1. Go to GitHub repository
2. Click "Actions" tab
3. Select workflow run
4. View logs and artifacts

---

## 🪝 Pre-commit Hooks

### Installation

```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks into git
pre-commit install

# (Optional) Run against all files
pre-commit run --all-files
```

### Hook Configuration

File: `.pre-commit-config.yaml`

Hooks included:
- Trailing whitespace
- End-of-file fixer
- YAML checker
- Large file detector
- Private key detection
- Black formatter
- isort import sorter
- flake8 linter
- Bandit security check
- pyupgrade Python syntax
- django-upgrade Django version upgrades

### Manual Hook Execution

```bash
# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Update hook versions
pre-commit autoupdate
```

---

## 📊 Coverage Report

### Generate Coverage Report

```bash
# Terminal report
pytest --cov --cov-report=term-missing

# HTML report
pytest --cov --cov-report=html
# View report: htmlcov/index.html

# XML report (for CI/CD)
pytest --cov --cov-report=xml

# Coverage threshold
# Fails if coverage < 70%
pytest --cov --cov-fail-under=70
```

### Viewing Coverage Report

1. Run pytest with coverage
2. Open `htmlcov/index.html` in browser
3. Click on modules to see coverage details
4. Red = uncovered, green = covered

---

## 🛠️ Test Fixtures & Setup

### conftest.py Fixtures

Located at project root, provides:

```python
@pytest.fixture
def client():
    """Django test client"""
    
@pytest.fixture
def user():
    """Create test user"""
    
@pytest.fixture
def authenticated_client(client, user):
    """Logged-in test client"""
    
@pytest.fixture
def setor():
    """Create test Setor"""
    
@pytest.fixture
def colaborador(user, setor):
    """Create test Colaborador"""
```

### Using Fixtures

```python
def test_with_fixtures(authenticated_client, colaborador):
    response = authenticated_client.get('/home/')
    assert response.status_code == 200
```

---

## ✅ Checklist Before Committing

- [ ] All tests pass: `pytest`
- [ ] Code formatted: `black .`
- [ ] Imports sorted: `isort .`
- [ ] No lint issues: `flake8 .`
- [ ] No security issues: `bandit -r .`
- [ ] Coverage threshold met: `pytest --cov --cov-fail-under=70`

Or simply run: `pre-commit run --all-files`

---

## 🚀 Best Practices

### Writing Tests

✅ **DO:**
- Test one thing per test
- Use descriptive test names
- Setup fixtures in setUp()
- Test both success and failure cases
- Use appropriate assertions

❌ **DON'T:**
- Test framework code (Django internals)
- Make tests interdependent
- Use magic values without explanation
- Test multiple concerns in one test
- Skip tests without reason

### Code Quality

✅ **DO:**
- Run pre-commit hooks before commit
- Keep coverage above 70%
- Fix security warnings
- Follow Django conventions
- Document complex logic

❌ **DON'T:**
- Ignore linting warnings
- Commit code with failing tests
- Skip security scans
- Leave unused imports
- Hardcode configuration

---

## 🔗 Related Documentation

- **Architecture:** See `CALIBRA_WEB_FINAL_SUMMARY.md`
- **Phase 8 Cleanup:** See `FASE_8_COMPLETA.md`
- **Project Status:** See `PROJECT_STATUS_CHECKPOINT.md`

---

## 📞 Troubleshooting

### Tests Fail with Import Error

```
ModuleNotFoundError: No module named 'metrologia'
```

**Solution:** Ensure INSTALLED_APPS in settings.py includes all modules

### Coverage Below Threshold

```
CoverageReport: Failed with coverage 65% (need 70%)
```

**Solution:** Write tests for uncovered code or lower threshold in pytest.ini

### Pre-commit Hook Fails

```
pre-commit hook FAILED at commit
```

**Solution:** Run `pre-commit run --all-files` to fix, then commit again

### Database Lock Error in Tests

```
DatabaseError: database is locked
```

**Solution:** Use SQLite with `--keepdb` option carefully, or use PostgreSQL

---

## 📚 Learning Resources

- [Django Testing Docs](https://docs.djangoproject.com/en/5.2/topics/testing/)
- [Pytest Django](https://pytest-django.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Pre-commit Framework](https://pre-commit.com/)

---

**Testing Framework:** ✅ READY  
**CI/CD Pipeline:** ✅ CONFIGURED  
**Pre-commit Hooks:** ✅ INSTALLED  
**Coverage Monitoring:** ✅ ENABLED

Next: Run `pytest` to validate the test suite! 🚀
