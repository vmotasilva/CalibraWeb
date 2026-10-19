import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def converter(apps, schema_editor):
    """Preserva dados: acompanhamento (texto) -> flag; parcial -> granularidade semanal/diária."""
    Indicador = apps.get_model('kpi', 'Indicador')
    Medicao = apps.get_model('kpi', 'Medicao')
    for ind in Indicador.objects.exclude(acompanhamento=''):
        ind.acompanhamento_detalhado = True
        ind.save(update_fields=['acompanhamento_detalhado'])
        gran = 'diaria' if ind.acompanhamento == 'diario' else 'semanal'
        Medicao.objects.filter(indicador=ind, parcial=True).update(granularidade=gran)
    Medicao.objects.filter(parcial=True, granularidade='mensal').update(granularidade='diaria')


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('kpi', '0002_alter_medicao_unique_together_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(name='medicao', unique_together=set()),
        migrations.AddField(
            model_name='indicador',
            name='acompanhamento_detalhado',
            field=models.BooleanField(default=False, help_text='Habilita os gráficos e lançamentos semanais e diários, além do mensal.', verbose_name='Acompanhar também por semana e por dia'),
        ),
        migrations.AddField(
            model_name='medicao',
            name='granularidade',
            field=models.CharField(choices=[('mensal', 'Mensal'), ('semanal', 'Semanal'), ('diaria', 'Diária')], default='mensal', max_length=8, verbose_name='Granularidade'),
        ),
        migrations.RunPython(converter, migrations.RunPython.noop),
        migrations.RemoveField(model_name='indicador', name='acompanhamento'),
        migrations.RemoveField(model_name='medicao', name='parcial'),
        migrations.AlterUniqueTogether(name='medicao', unique_together={('indicador', 'periodo', 'granularidade')}),
        migrations.CreateModel(
            name='Motivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(verbose_name='Data')),
                ('descricao', models.CharField(max_length=200, verbose_name='Motivo')),
                ('quantidade', models.DecimalField(decimal_places=2, default=1, max_digits=14, verbose_name='Quantidade')),
                ('indicador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='motivos', to='kpi.indicador')),
                ('registrado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Motivo',
                'verbose_name_plural': 'Motivos',
                'ordering': ['-data', 'descricao'],
            },
        ),
    ]
