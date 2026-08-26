import re

with open('auditoria/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = r"'evidencias': evidencias_ativas or [""Evidência objetiva de não conformidade ao requisito.""],"
new_str = r"'evidencias_nc': evidencias_nc or [""Evidência objetiva de não conformidade ao requisito.""]," + '\n' + r"                    'evidencias_om': evidencias_om,"

content = content.replace(old_str, new_str)

old_str2 = r"'amostras_conformes': amostras_conformes[:2]"
new_str2 = r"'amostras_conformes': amostras_conformes"

content = content.replace(old_str2, new_str2)

with open('auditoria/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
