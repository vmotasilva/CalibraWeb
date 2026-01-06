#!/bin/bash
echo "TESTE 1: ENTRYPOINT INICIADO"
sleep 2
echo "TESTE 2: APÓS SLEEP"
python --version
echo "TESTE 3: PYTHON OK"
gunicorn --version
echo "TESTE 4: GUNICORN OK"

# Try to import Django
python -c "import django; print('TESTE 5: DJANGO OK')"

echo "TESTE 6: INICIANDO GUNICORN"
exec gunicorn \
  config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 1 \
  --worker-class sync \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
