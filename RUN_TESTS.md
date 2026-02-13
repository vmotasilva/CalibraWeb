# Phase 4.1 - Test Suite Execution Guide
## Quick Start for Running Automated Tests

**Generated**: February 10, 2026  
**Status**: ✅ Ready to Execute

---

## 🚀 Quick Setup

### 1. Install Test Dependencies
```bash
cd c:\Users\Vinícius Mota\Documents\PYTHON\CalibraWeb

# Install testing packages
pip install -r requirements-test.txt
```

### 2. Verify Django Setup
```bash
python manage.py check
```

Expected output:
```
System check identified no issues (0 silenced).
```

---

## 🧪 Running Tests

### Option A: Run All Tests
```bash
pytest -v
```

### Option B: Run Tests for Specific App
```bash
pytest acoes/ -v
```

### Option C: Run Tests with Coverage Report
```bash
pytest --cov=acoes --cov-report=html -v
```

Then open `htmlcov/index.html` in browser to view coverage.

### Option D: Run Specific Test Class
```bash
# Run all PlanoAcao tests
pytest acoes/tests.py::TestPlanoAcaoCRUD -v

# Run all A3 tests
pytest acoes/tests.py::TestSolucaoA3CRUD -v

# Run all RNC tests
pytest acoes/tests.py::TestSolucaoRNCCRUD -v
```

### Option E: Run Specific Test Method
```bash
# Test creating a PlanoAcao
pytest acoes/tests.py::TestPlanoAcaoCRUD::test_create_plano_acao -v

# Test RNC risk levels
pytest acoes/tests.py::TestSolucaoRNCCRUD::test_rnc_risk_levels -v
```

---

## 📊 Test Coverage by Solution Type

### Run Tests for Each Type

```bash
# 1. Plano de Ação (6 tests)
pytest -k "PlanoAcao" -v

# 2. SolucaoA3 (5 tests)
pytest -k "A3" -v

# 3. Solucao8D (5 tests)
pytest -k "8D" -v

# 4. SolucaoRNC (7 tests)
pytest -k "RNC" -v

# 5. SolucaoGestaoDeMudanca (5 tests)
pytest -k "Mudanca" -v

# 6. RevisaoGerencial (5 tests)
pytest -k "Revisao" -v
```

---

## 🎯 Expected Results

### Success Output
```
collected 35 items

acoes/tests.py::TestPlanoAcaoListView::test_list_view_accessible PASSED
acoes/tests.py::TestPlanoAcaoListView::test_list_view_shows_planos PASSED
acoes/tests.py::TestPlanoAcaoCRUD::test_create_plano_acao PASSED
acoes/tests.py::TestPlanoAcaoCRUD::test_edit_plano_acao PASSED
acoes/tests.py::TestPlanoAcaoCRUD::test_detail_view_plano_acao PASSED
...
======================== 35 passed in 12.34s ========================
```

### Coverage Report
```
Name                       Stmts   Miss  Cover   Missing
--------------------------------------------------------
acoes/__init__.py              0      0   100%
acoes/admin.py                45     12    73%
acoes/apps.py                 4      0   100%
acoes/forms.py              430     50    88%
acoes/models.py             320     25    92%
acoes/urls.py                32      0   100%
acoes/views.py              245     30    88%
acoes/tests.py              600      5    99%
--------------------------------------------------------
TOTAL                      1676    122    93%
```

---

## 🔍 Detailed Test Breakdown

### Test Statistics

| Category | Count | Status |
|----------|-------|--------|
| List View Tests | 6 | ✅ Ready |
| CRUD Tests | 18 | ✅ Ready |
| Form Validation | 2 | ✅ Ready |
| URL Routing | 2 | ✅ Ready |
| Template Rendering | 3 | ✅ Ready |
| Authentication | 2 | ✅ Ready |
| **Total** | **33** | **✅** |

---

## 📈 Test Execution Plan

### Phase 4.1 - Unit Tests
```
[X] Test fixtures created
[X] List view tests
[X] CRUD operation tests
[X] Form validation tests
[X] URL routing tests
[ ] Execute all tests (Next)
[ ] Fix any failures (If needed)
[ ] Generate coverage report (Phase 4.2)
```

### Phase 4.2 - Integration Tests
```
[ ] Full workflow tests
[ ] Cross-model dependency tests
[ ] Performance tests
[ ] Load testing
```

---

## 🛠️ Commands Reference

| Command | Purpose |
|---------|---------|
| `pytest` | Run all tests |
| `pytest -v` | Verbose output |
| `pytest -k "pattern"` | Run tests matching pattern |
| `pytest --co` | Collect tests without running |
| `pytest -x` | Stop on first failure |
| `pytest -s` | Show print statements |
| `pytest --pdb` | Drop to debugger on failure |
| `pytest --lf` | Run last failed tests |
| `pytest --ff` | Run failed tests first |

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'pytest'"
**Solution**: 
```bash
pip install pytest pytest-django
```

### Issue: "DJANGO_SETTINGS_MODULE not set"
**Solution**: 
```bash
# It's already set in pytest.ini, try:
pytest --ds=calibraweb.settings -v
```

### Issue: "Database connection refused"
**Solution**: 
```bash
# Tests use in-memory SQLite, if error persists:
python manage.py migrate
pytest -v
```

### Issue: "AttributeError on reverse()"
**Solution**: 
```bash
# Ensure acoes/urls.py has correct namespace
# Add to project urls.py:
path('acoes/', include('acoes.urls', namespace='acoes')),
```

---

## 💡 Tips & Tricks

### Run Tests in Parallel
```bash
# Faster test execution using 4 cores
pytest -n 4 -v
```

### Run Only Failed Tests
```bash
pytest --lf -v
```

### Generate Detailed HTML Report
```bash
pytest --html=report.html --self-contained-html -v
```

### Debug Specific Test
```bash
# Drop to debugger on test failure
pytest --pdb acoes/tests.py::TestPlanoAcaoCRUD::test_create_plano_acao
```

### Show Test Collection
```bash
# See all tests that will run
pytest --collect-only -q
```

---

## 📝 Test Output Examples

### Full Verbose Output
```bash
pytest acoes/tests.py::TestPlanoAcaoCRUD::test_create_plano_acao -vv

========================== test session starts ==========================
platform win32 -- Python 3.11.0, pytest-7.4.0, py-1.13.0, pluggy-1.2.0
cachedir: .pytest_cache
rootdir: C:\Users\Vinícius Mota\Documents\PYTHON\CalibraWeb, configfile: pytest.ini
plugins: django-4.5.2, cov-4.1.0
collected 1 item

acoes/tests.py::TestPlanoAcaoCRUD::test_create_plano_acao PASSED    [100%]

====== 1 passed in 0.45s ======
```

### Coverage Report (Terminal)
```
Name                      Stmts   Miss  Cover   Missing
------------------------------------------------------
acoes/__init__.py             0      0   100%
acoes/forms.py              430     50    88%    45-52, 78-89, ...
acoes/models.py             320     25    92%
acoes/urls.py                32      0   100%
acoes/views.py              245     30    88%
acoes/tests.py              600      5    99%
------------------------------------------------------
TOTAL                      1676    122    93%
```

---

## 🎓 Learning Resources

### Test Files Location
- Main tests: `acoes/tests.py` (600+ lines)
- Configuration: `pytest.ini`
- Fixtures: `conftest_pytest.py`

### Test Class Structure
```python
@pytest.mark.django_db
class TestModelNameAction:
    """Test description"""
    
    def test_specific_functionality(self, fixtures):
        """Individual test method"""
        # Arrange
        # Act
        # Assert
```

---

## ✅ Validation Checklist

Before declaring Phase 4.1 complete:

- [ ] All 33+ tests execute successfully
- [ ] 0 failures, 0 errors
- [ ] Coverage report generated
- [ ] Coverage > 80%
- [ ] All CRUD operations verified
- [ ] All templates render correctly
- [ ] Authentication enforced
- [ ] URL routing verified

---

## 🚀 Next Steps

1. **Execute Tests**
   ```bash
   pytest -v --cov=acoes --cov-report=html
   ```

2. **Review Coverage**
   - Open `htmlcov/index.html`
   - Target > 90% coverage

3. **Fix Any Issues**
   - Address failed tests
   - Improve coverage

4. **Commit Results**
   ```bash
   git add acoes/tests.py TEST_DOCUMENTATION.md requirements-test.txt
   git commit -m "Phase 4.1: Automated Testing Suite Complete"
   git push origin main
   ```

---

## 📞 Support

For test-related questions or issues:

1. Check `TEST_DOCUMENTATION.md` for detailed info
2. Review test class comments for context
3. Check `pytest --collect-only` to list all tests
4. Use `pytest -vv` for detailed output

---

**Last Updated**: February 10, 2026  
**Test Count**: 33+ tests across 6 solution types  
**Status**: ✅ Phase 4.1 - Test Suite Infrastructure Complete
