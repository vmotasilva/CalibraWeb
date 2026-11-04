from django.db import migrations


def semear(apps, schema_editor):
    Kpi = apps.get_model('kpi', 'KpiHierarquico')
    Setor = apps.get_model('kpi', 'HierSetor')
    kpi, _ = Kpi.objects.get_or_create(nome='Insumos', defaults={'descricao': 'Consumo de insumos por setor, máquina e item'})
    for n, nome in enumerate(['Surfaçagem', 'HMC', 'Montagem']):
        Setor.objects.get_or_create(kpi=kpi, nome=nome, defaults={'ordem': n})


class Migration(migrations.Migration):
    dependencies = [('kpi', '0025_kpi_hierarquico')]
    operations = [migrations.RunPython(semear, migrations.RunPython.noop)]
