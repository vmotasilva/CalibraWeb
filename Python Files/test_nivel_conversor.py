#!/usr/bin/env python
"""Teste de conversão de níveis N/A"""

niveis = ["n/a", "N/A", "na", "NA", "-1", "0", "1", "2", "3"]

print("Teste de conversão de Nível de Competência:")
print("=" * 50)

for nivel_str in niveis:
    nivel_str_lower = nivel_str.lower().strip()
    if nivel_str_lower in ['n/a', 'na', '-1']:
        nivel = -1
    else:
        nivel = int(nivel_str)
    print(f"'{nivel_str}' -> {nivel}")

print("=" * 50)
print("✓ Todos os valores foram convertidos com sucesso!")
