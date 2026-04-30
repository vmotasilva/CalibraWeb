import os
import sys
import unicodedata
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from acoes.models import AcaoCorretiva

def normalize_spaces(value):
    return " ".join(value.split())

def status_key(value):
    value = normalize_spaces(value).lower().replace("_", " ")
    value = "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )
    return value

status_map = {
    "aberta": "aberta",
    "aberto": "aberta",
    "em progresso": "em_progresso",
    "em andamento": "em_progresso",
    "concluida": "concluida",
    "concluido": "concluida",
    "cancelada": "cancelada",
    "cancelado": "cancelada",
    "atrasado": "aberta",
}

updated = 0
unknown_status = set()

for acao in AcaoCorretiva.objects.all():
    fields_to_update = []

    if acao.status:
        key = status_key(acao.status)
        new_status = status_map.get(key)
        if new_status and new_status != acao.status:
            acao.status = new_status
            fields_to_update.append("status")
        elif not new_status:
            unknown_status.add(acao.status)

    if acao.tipo_solucao:
        new_tipo_solucao = normalize_spaces(acao.tipo_solucao)
        if new_tipo_solucao != acao.tipo_solucao:
            acao.tipo_solucao = new_tipo_solucao
            fields_to_update.append("tipo_solucao")

    if acao.origem:
        new_origem = normalize_spaces(acao.origem)
        if new_origem != acao.origem:
            acao.origem = new_origem
            fields_to_update.append("origem")

    if fields_to_update:
        acao.save(update_fields=fields_to_update)
        updated += 1

print(f"Updated records: {updated}")

if unknown_status:
    print("Unknown status values found:")
    for value in sorted(unknown_status):
        print(f"  - {value}")
else:
    print("No unknown status values found.")
