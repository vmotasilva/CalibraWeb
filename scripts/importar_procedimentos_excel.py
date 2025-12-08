import os
import django
import pandas as pd
from datetime import datetime

# Ajuste o caminho do settings se necessário
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from training.models import Procedimento, Area
from organization.models import Setor

# Caminho do arquivo Excel
EXCEL_PATH = 'database/incoming/Aco_treinamentos_2025.xlsm'
SHEET_NAME = 0  # ou o nome da aba se necessário

# Mapeamento de colunas do Excel para campos do modelo
COLUMN_MAP = {
    'Código': 'codigo',
    'Título': 'titulo',
    'Revisão': 'revisao_atual',
    'Data Revisão': 'data_revisao',
    'Data Aprovação': 'data_aprovacao_revisao',
    'Tipo': 'tipo',
    'Setor': 'setor',
    'Área': 'area',
}

# Função para buscar ou criar Setor/Área

def get_or_none(model, nome):
    if not nome or pd.isna(nome):
        return None
    obj, _ = model.objects.get_or_create(nome=nome.strip().upper())
    return obj

def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None

def main():
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    for _, row in df.iterrows():
        data = {}
        for col_excel, field in COLUMN_MAP.items():
            val = row.get(col_excel)
            if field == 'setor':
                data['setor'] = get_or_none(Setor, val)
            elif field == 'area':
                data['area'] = get_or_none(Area, val)
            elif field in ['data_revisao', 'data_aprovacao_revisao']:
                data[field] = parse_date(val)
            elif field in ['codigo', 'titulo', 'tipo', 'revisao_atual']:
                data[field] = str(val).strip().upper() if pd.notna(val) else ''
        if not data.get('codigo'):
            continue  # pula linhas sem código
        proc, created = Procedimento.objects.get_or_create(codigo=data['codigo'], defaults=data)
        if not created:
            for k, v in data.items():
                setattr(proc, k, v)
            proc.save()
        print(f"{'Criado' if created else 'Atualizado'}: {proc.codigo} - {proc.titulo}")

if __name__ == '__main__':
    main()
