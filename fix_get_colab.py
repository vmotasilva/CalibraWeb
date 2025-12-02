#!/usr/bin/env python3
"""Script para remover todas as chamadas a get_colab do views.py"""
import re

file_path = 'qms/views.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Substituições
replacements = [
    # dashboard_view
    (r'(@login_required\ndef dashboard_view\(request\):\n    )colab = get_colab\(request\)\n    nome_display = colab\.nome_completo if colab else request\.user\.username',
     r'\1nome_display = request.user.username'),
    (r'"colaborador": colab,\n        ', ''),
    
    # modulo_metrologia_view
    (r'(@login_required\ndef modulo_metrologia_view\(request\):\n    )colab = get_colab\(request\)\n\n    ',
     r'\1'),
    
    # modulo_rh_view
    (r'(@login_required\ndef modulo_rh_view\(request\):\n    )colab = get_colab\(request\)',
     r'\1colab = None\n    try:\n        colab = Colaborador.objects.filter(user_django=request.user).first()\n    except Exception:\n        pass'),
    
    # detalhe_colaborador_view, editar_colaborador_view, novo_colaborador_view
    (r'(def (?:detalhe|editar|novo)_colaborador_view\(request[^)]*\):\n    )usuario_logado = get_colab\(request\)',
     r'\1usuario_logado = None\n    try:\n        usuario_logado = Colaborador.objects.filter(user_django=request.user).first()\n    except Exception:\n        pass'),
    
    # Remover "colaborador": get_colab(request) de todos os contextos
    (r'"colaborador": get_colab\(request\),?\s*', ''),
    (r"'colaborador': get_colab\(request\),?\s*", ''),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Substituições concluídas!")
