#!/usr/bin/env python
"""Teste simples da view de gestão de férias"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.views.generic import View
from rh.views.views import gestao_ferias_view
import inspect

# Verificar se a view existe
print("✅ View gestao_ferias_view importada com sucesso")
print(f"Tipo: {type(gestao_ferias_view)}")
print(f"Módulo: {gestao_ferias_view.__module__}")

# Ver código-fonte
try:
    source_lines = inspect.getsource(gestao_ferias_view)
    print(f"\n✅ Função tem {len(source_lines.splitlines())} linhas")
    # Mostrar primeira e última linha
    lines = source_lines.splitlines()
    print(f"Primeira linha: {lines[0]}")
    print(f"Última linha: {lines[-1]}")
except Exception as e:
    print(f"❌ Erro ao obter fonte: {e}")
