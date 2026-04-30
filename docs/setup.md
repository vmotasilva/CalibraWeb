# Setup Local - CalibraWEB

## Pré-requisitos

- Python 3.11+
- PostgreSQL 14+ (ou SQLite para desenvolvimento)
- Redis 6+
- Git

## Instalação Passo a Passo

### 1. Clonar Repositório

```bash
git clone https://github.com/seu-usuario/CalibraWeb.git
cd CalibraWeb
```

### 2. Criar Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

```bash
# Copiar template
cp .env.example .env

# Editar .env com suas configurações
# Importante: DATABASE_URL, SECRET_KEY, DEBUG
```

### 5. Executar Migrações

```bash
python manage.py migrate
```

### 6. Criar Superuser (Admin)

```bash
python manage.py createsuperuser
```

### 7. Coletar Arquivos Estáticos

```bash
python manage.py collectstatic --noinput
```

### 8. Iniciar Servidor Local

```bash
python manage.py runserver 0.0.0.0:8000
```

Acessar: http://localhost:8000

## Executar Celery Localmente

### Terminal 1: Worker

```bash
celery -A config worker -l info
```

### Terminal 2: Beat (opcional)

```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Terminal 3: Flower (Monitoring)

```bash
celery -A config flower --port=5555
```

Acessar Flower: http://localhost:5555

## Testes

```bash
# Rodar todos os testes
pytest

# Rodar com cobertura
pytest --cov=core --cov=rh --cov=metrologia

# Rodar teste específico
pytest tests/core/test_models.py::test_specific_function
```

## Linting & Formatação

```bash
# Verificar estilo
flake8 . --max-line-length=120

# Formatar código
black . --line-length=120

# Ordenar imports
isort .

# Análise de segurança
bandit -r core rh metrologia
```

## Troubleshooting

### Erro: "No module named 'django'"
```bash
pip install -r requirements.txt
```

### Erro de Banco de Dados
```bash
python manage.py migrate --fake-initial
```

### Redis não conecta
```bash
# Verificar se Redis está rodando
redis-cli ping
```

---

Para mais informações sobre arquitetura, consulte [Arquitetura](./arquitetura.md)
