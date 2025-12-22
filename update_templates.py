#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Atualizar templates de procedures para usar {% block main_content %}"""

import os

templates_dir = r"C:\CalibraWeb\procedures\templates\procedures"
files_to_update = [
    "procedimento_lista.html",
    "procedimento_detalhe.html",
    "procedimento_detail.html",
    "procedimento_form.html",
    "treinamento_lista.html",
    "treinamento_detalhe.html",
    "treinamento_form.html",
    "fornecedor_lista.html",
    "fornecedor_detalhe.html",
    "fornecedor_form.html",
    "cotacao_form.html",
    "cotacao_detalhe.html",
    "orcamento_form.html",
    "avaliacao_fornecedor_form.html"
]

count = 0
for filename in files_to_update:
    filepath = os.path.join(templates_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Substituir {% block content %} por {% block main_content %}
        if '{% block content %}' in content:
            content = content.replace('{% block content %}', '{% block main_content %}')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✓ {filename} - atualizado")
            count += 1
        else:
            print(f"⚠ {filename} - já estava atualizado ou não encontrado")
    else:
        print(f"✗ {filename} - arquivo não encontrado")

print(f"\nTotal atualizado: {count}")
