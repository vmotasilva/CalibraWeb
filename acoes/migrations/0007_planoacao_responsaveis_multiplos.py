# Generated migration for adding M2M responsaveis_multiplos to PlanoAcao

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0013_remove_ferias_periodo_aquisitivo'),
        ('acoes', '0006_refactor_a3_revisao_gerencial'),
    ]

    operations = [
        migrations.AddField(
            model_name='planoacao',
            name='responsaveis_multiplos',
            field=models.ManyToManyField(blank=True, related_name='planos_acao_multiplos', to='rh.colaborador', verbose_name='Responsáveis (Múltiplos)'),
        ),
        migrations.AlterField(
            model_name='planoacao',
            name='responsavel_acao',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='planos_acao', to='rh.colaborador', verbose_name='Responsável (Legado)'),
        ),
    ]
