# -*- coding: utf-8 -*-
from django.db import migrations, models


def seed_tipo_solucao(apps, schema_editor):
    TipoSolucao = apps.get_model('acoes', 'TipoSolucao')
    defaults = [
        'Plano de Ação',
        'A3',
        '8D',
        'RNC',
        'Gestão de Mudança',
        'Revisão Gerencial',
    ]
    for nome in defaults:
        TipoSolucao.objects.get_or_create(nome=nome, defaults={'ativo': True})


def unseed_tipo_solucao(apps, schema_editor):
    TipoSolucao = apps.get_model('acoes', 'TipoSolucao')
    defaults = [
        'Plano de Ação',
        'A3',
        '8D',
        'RNC',
        'Gestão de Mudança',
        'Revisão Gerencial',
    ]
    TipoSolucao.objects.filter(nome__in=defaults).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('acoes', '0017_alter_acaocorretiva_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoSolucao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True, verbose_name='Nome do Tipo')),
                ('descricao', models.TextField(blank=True, null=True, verbose_name='Descricao')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Tipo de Solucao',
                'verbose_name_plural': 'Tipos de Solucao',
                'ordering': ['nome'],
            },
        ),
        migrations.AddIndex(
            model_name='tiposolucao',
            index=models.Index(fields=['nome'], name='acoes_tipo_nome_idx'),
        ),
        migrations.AddIndex(
            model_name='tiposolucao',
            index=models.Index(fields=['ativo'], name='acoes_tipo_ativo_idx'),
        ),
        migrations.RunPython(seed_tipo_solucao, reverse_code=unseed_tipo_solucao),
    ]
