#!/bin/bash
# Script para rodar testes Django usando ambiente de testes
export $(grep -v '^#' .env.test | xargs)
python manage.py test
