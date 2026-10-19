from django.db import migrations, models


def converter(apps, schema_editor):
    """Preserva o que já aparecia: semanal/diário seguem o flag antigo; motivos ficam habilitados onde já há lançamentos."""
    Indicador = apps.get_model('kpi', 'Indicador')
    Motivo = apps.get_model('kpi', 'Motivo')
    for ind in Indicador.objects.all():
        ind.exibir_semanal = ind.exibir_diario = bool(ind.acompanhamento_detalhado)
        usados = set(Motivo.objects.filter(indicador=ind).values_list('granularidade', flat=True).distinct())
        ind.motivos_diario = 'diaria' in usados
        ind.motivos_semanal = 'semanal' in usados
        ind.motivos_mensal = 'mensal' in usados
        ind.save()


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0006_campos_formula_dados'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicador',
            name='exibir_diario',
            field=models.BooleanField(default=False, verbose_name='Gráfico dia a dia'),
        ),
        migrations.AddField(
            model_name='indicador',
            name='exibir_mensal',
            field=models.BooleanField(default=True, verbose_name='Gráfico mês a mês'),
        ),
        migrations.AddField(
            model_name='indicador',
            name='exibir_semanal',
            field=models.BooleanField(default=False, verbose_name='Gráfico semana a semana'),
        ),
        migrations.AddField(
            model_name='indicador',
            name='motivos_diario',
            field=models.BooleanField(default=False, verbose_name='Tabela de motivos — Diário'),
        ),
        migrations.AddField(
            model_name='indicador',
            name='motivos_mensal',
            field=models.BooleanField(default=False, verbose_name='Tabela de motivos — Mensal'),
        ),
        migrations.AddField(
            model_name='indicador',
            name='motivos_semanal',
            field=models.BooleanField(default=False, verbose_name='Tabela de motivos — Semanal'),
        ),
        migrations.RunPython(converter, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='indicador',
            name='acompanhamento_detalhado',
        ),
    ]
