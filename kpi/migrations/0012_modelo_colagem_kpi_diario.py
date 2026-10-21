from django.db import migrations

NOME = 'KPI Diário'
# Ordem das 32 posições da tela "KPI Diário" (botão "Copiar Valores do KPI"). Só rótulos: o vínculo de cada
# posição com indicador/variável é feito depois, na edição do modelo (Rótulo | Indicador | Variável | Setor).
POSICOES = [
    'TOTAL PEDIDOS - ENTRADA',
    'TOTAL LENTES - ENTRADA',
    'TOTAL PEDIDOS - SAIDA',
    'TOTAL LENTES - ENVIADAS',
    'TOTAL LENTES - ENVIADAS NO PRAZO',
    'TOTAL LENTES - ENVIADAS COM ATRAZO ATE 2',
    'TOTAL LENTES - ENVIADAS COM ATRAZO > 2',
    'TOTAL LENTES - ENVIADAS COM ATRAZO > 5',
    'TOTAL LENTES - ENVIADAS COM ATRAZO > 10',
    'OS - APENAS SURFACAGEM',
    'OS - APENAS SURFACAGEM + HMC',
    'OS - APENAS SURFACAGEM + MONTAGEM',
    'OS - APENAS SURFACAGEM + HMC + MONTAGEM',
    'OS - APENAS SURFACAGEM + COLORACAO',
    'OS - APENAS MONTAGEM',
    'OS - APENAS COLORACAO',
    'OS - APENAS COLORACAO + MONTAGEM',
    'OS - HMC CLIENTE',
    'INVENTARIO - TOTAL PEDIDOS - ENTRADA',
    'INVENTARIO - NAO ATENDIDOS (SF/FSV)',
    'SURFACAGEM - ENTRADA',
    'SURFACAGEM - LENTES BOAS',
    'SURFACAGEM - LENTES QUEBRADAS',
    'HC - ENTRADA',
    'HC - LENTES BOAS',
    'HC - LENTES QUEBRADAS',
    'AR - ENTRADA',
    'AR - LENTES BOAS',
    'AR - LENTES QUEBRADAS',
    'E_M - ENTRADA',
    'E_M - LENTES BOAS',
    'E_M - LENTES QUEBRADAS',
]


def forwards(apps, schema_editor):
    Modelo = apps.get_model('kpi', 'ModeloColagem')
    if not Modelo.objects.filter(nome__iexact=NOME).exists():
        Modelo.objects.create(nome=NOME, linhas='\n'.join(POSICOES))


class Migration(migrations.Migration):

    dependencies = [('kpi', '0011_modelo_colagem')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
