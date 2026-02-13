# Generated migration for adding standard fields to Solucao8D

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0013_remove_ferias_periodo_aquisitivo'),
        ('acoes', '0008_solucaoa3_standard_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='solucao8d',
            name='acao_eficaz',
            field=models.CharField(blank=True, choices=[('eficaz', 'Eficaz'), ('nao_eficaz', 'Não Eficaz')], max_length=20, null=True, verbose_name='Ação Eficaz?'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='classificacao',
            field=models.CharField(blank=True, choices=[('corretiva', 'Corretiva'), ('preventiva', 'Preventiva'), ('melhoria', 'Melhoria')], max_length=20, null=True, verbose_name='Classificação'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='comentarios',
            field=models.TextField(blank=True, null=True, verbose_name='Comentários'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='data_primeira_deadline',
            field=models.DateField(blank=True, null=True, verbose_name='1º Deadline'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='input_origem',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Input/Origem'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='kpi',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='KPI'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='laboratorio',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Laboratório'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='numero_acao',
            field=models.IntegerField(blank=True, null=True, verbose_name='Nº Ação'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='prioridade',
            field=models.BooleanField(default=False, verbose_name='Prioridade (Y/N)'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='responsaveis_multiplos',
            field=models.ManyToManyField(blank=True, related_name='solucoes_8d_responsaveis', to='rh.colaborador', verbose_name='Responsáveis (Múltiplos)'),
        ),
        migrations.AddField(
            model_name='solucao8d',
            name='status',
            field=models.CharField(choices=[('planejada', 'Planejada'), ('em_curso', 'Em Curso/Andamento'), ('completa', 'Completa/Concluído'), ('retardo', 'Retardo/Atrasada'), ('cancelada', 'Cancelada')], default='planejada', max_length=20, verbose_name='Status'),
        ),
    ]
