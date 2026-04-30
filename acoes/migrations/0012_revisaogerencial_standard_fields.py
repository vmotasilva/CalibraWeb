# Generated migration for adding standard fields to RevisaoGerencial

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0013_remove_ferias_periodo_aquisitivo'),
        ('acoes', '0011_solucaogestaodemudanca_standard'),
    ]

    operations = [
        migrations.AddField(
            model_name='revisaogerencial',
            name='acao_eficaz',
            field=models.CharField(blank=True, choices=[('eficaz', 'Eficaz'), ('nao_eficaz', 'Não Eficaz')], max_length=20, null=True, verbose_name='Ação Eficaz?'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='classificacao',
            field=models.CharField(blank=True, choices=[('corretiva', 'Corretiva'), ('preventiva', 'Preventiva'), ('melhoria', 'Melhoria')], max_length=20, null=True, verbose_name='Classificação'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='comentarios',
            field=models.TextField(blank=True, null=True, verbose_name='Comentários'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='data_primeira_deadline',
            field=models.DateField(blank=True, null=True, verbose_name='1º Deadline'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='descricao',
            field=models.TextField(blank=True, null=True, verbose_name='Descrição'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='input_origem',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Input/Origem'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='kpi',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='KPI'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='numero_acao',
            field=models.IntegerField(blank=True, null=True, verbose_name='Nº Ação'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='prioridade',
            field=models.BooleanField(default=False, verbose_name='Prioridade (Y/N)'),
        ),
        migrations.AddField(
            model_name='revisaogerencial',
            name='responsaveis_multiplos',
            field=models.ManyToManyField(blank=True, related_name='revisoes_gerenciais_responsaveis', to='rh.colaborador', verbose_name='Responsáveis (Múltiplos)'),
        ),
    ]
