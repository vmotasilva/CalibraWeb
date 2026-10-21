from django.db import migrations


def forwards(apps, schema_editor):
    """Cada causa/análise já registrada vira o primeiro card do período."""
    AnaliseCausa = apps.get_model('kpi', 'AnaliseCausa')
    AnaliseItem = apps.get_model('kpi', 'AnaliseItem')
    for a in AnaliseCausa.objects.filter(dispensada=False).exclude(causa='', analise=''):
        if not AnaliseItem.objects.filter(registro=a).exists():
            AnaliseItem.objects.create(registro=a, ordem=0, causa=a.causa, analise=a.analise)


class Migration(migrations.Migration):

    dependencies = [('kpi', '0018_analise_item')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
