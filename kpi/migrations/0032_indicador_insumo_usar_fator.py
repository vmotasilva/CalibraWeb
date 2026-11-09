from django.db import migrations, models


def preservar_indicadores_existentes(apps, schema_editor):
    """Até aqui o consumo dos indicadores já era quantidade × fator: os existentes continuam assim."""
    apps.get_model('kpi', 'IndicadorInsumo').objects.update(usar_fator=True)


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0031_indicador_insumo_periodicidade'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicadorinsumo',
            name='usar_fator',
            field=models.BooleanField(default=False, help_text='Consumo = quantidade × fator de conversão do código (ex.: fita em metros). Desmarcado, o consumo é em unidades.', verbose_name='Aplicar o fator dos códigos'),
        ),
        migrations.RunPython(preservar_indicadores_existentes, migrations.RunPython.noop),
    ]
