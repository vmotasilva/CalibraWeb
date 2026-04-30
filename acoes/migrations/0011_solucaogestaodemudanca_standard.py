# Generated migration for adding standard fields to SolucaoGestaoDeMudanca

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0013_remove_ferias_periodo_aquisitivo'),
        ('acoes', '0010_solucaornc_standard_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='acao_eficaz',
            field=models.CharField(blank=True, choices=[('eficaz', 'Eficaz'), ('nao_eficaz', 'Não Eficaz')], max_length=20, null=True, verbose_name='Ação Eficaz?'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='classificacao',
            field=models.CharField(blank=True, choices=[('corretiva', 'Corretiva'), ('preventiva', 'Preventiva'), ('melhoria', 'Melhoria')], max_length=20, null=True, verbose_name='Classificação'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='comentarios',
            field=models.TextField(blank=True, null=True, verbose_name='Comentários'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='data_primeira_deadline',
            field=models.DateField(blank=True, null=True, verbose_name='1º Deadline'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='descricao_acao',
            field=models.TextField(blank=True, null=True, verbose_name='Descrição'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='input_origem',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Input/Origem'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='kpi',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='KPI'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='laboratorio_acao',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Laboratório'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='numero_acao',
            field=models.IntegerField(blank=True, null=True, verbose_name='Nº Ação'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='prioridade',
            field=models.BooleanField(default=False, verbose_name='Prioridade (Y/N)'),
        ),
        migrations.AddField(
            model_name='solucaogestaodemudanca',
            name='responsaveis_multiplos',
            field=models.ManyToManyField(blank=True, related_name='gestoes_mudanca_responsaveis', to='rh.colaborador', verbose_name='Responsáveis (Múltiplos)'),
        ),
    ]
