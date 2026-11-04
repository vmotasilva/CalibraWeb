import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def mover_itens_para_subcategoria_geral(apps, schema_editor):
    """Os itens que já existiam ficavam direto na categoria: passam para uma subcategoria 'Geral' dela (nada se perde)."""
    Item = apps.get_model('kpi', 'HierItem')
    Sub = apps.get_model('kpi', 'HierSubcategoria')
    geral = {}
    for item in Item.objects.all():
        sub = geral.get(item.categoria_id)
        if sub is None:
            sub, _ = Sub.objects.get_or_create(categoria_id=item.categoria_id, nome='Geral')
            geral[item.categoria_id] = sub
        item.subcategoria = sub
        item.save(update_fields=['subcategoria'])


class Migration(migrations.Migration):

    dependencies = [
        ('kpi', '0027_decide'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # O antigo "subcategoria" (item avaliado) vira HierItem; "HierSubcategoria" passa a ser o nível entre categoria e item.
        migrations.AlterField(
            model_name='hiersubcategoria', name='categoria',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens_antigos', to='kpi.hiercategoria'),
        ),
        migrations.RenameModel(old_name='HierSubcategoria', new_name='HierItem'),
        migrations.RenameField(model_name='hierconsumo', old_name='subcategoria', new_name='item'),
        migrations.CreateModel(
            name='HierSubcategoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, verbose_name='Subcategoria')),
                ('ordem', models.PositiveIntegerField(default=0)),
                ('categoria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subcategorias', to='kpi.hiercategoria')),
            ],
            options={
                'verbose_name': 'Subcategoria (KPI por setor)',
                'verbose_name_plural': 'Subcategorias (KPI por setor)',
                'ordering': ['ordem', 'nome'],
                'unique_together': {('categoria', 'nome')},
            },
        ),
        migrations.AddField(
            model_name='hieritem', name='subcategoria',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='kpi.hiersubcategoria'),
        ),
        migrations.RunPython(mover_itens_para_subcategoria_geral, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(name='hieritem', unique_together=set()),
        migrations.RemoveField(model_name='hieritem', name='categoria'),
        migrations.AlterField(
            model_name='hieritem', name='subcategoria',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='itens', to='kpi.hiersubcategoria'),
        ),
        migrations.AlterUniqueTogether(name='hieritem', unique_together={('subcategoria', 'nome')}),
        migrations.AlterModelOptions(
            name='hieritem',
            options={'ordering': ['ordem', 'nome'], 'verbose_name': 'Item (KPI por setor)', 'verbose_name_plural': 'Itens (KPI por setor)'},
        ),
        migrations.AlterField(model_name='hieritem', name='nome', field=models.CharField(max_length=100, verbose_name='Item avaliado')),
        migrations.AddField(
            model_name='hierconsumo', name='origem',
            field=models.CharField(choices=[('manual', 'Manual'), ('importado', 'Importado')], default='manual', max_length=10, verbose_name='Origem'),
        ),
        migrations.CreateModel(
            name='HierCodigo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.PositiveIntegerField(unique=True, verbose_name='Código')),
                ('descricao', models.CharField(blank=True, max_length=300, verbose_name='Material / referência')),
                ('unidade', models.CharField(blank=True, max_length=20, verbose_name='Unidade do almoxarifado')),
                ('familia', models.CharField(blank=True, max_length=100, verbose_name='Família (almoxarifado)')),
                ('fator', models.DecimalField(decimal_places=6, default=1, help_text='Multiplica a quantidade do código para chegar na unidade do item (ex.: galão → litros).', max_digits=14, verbose_name='Fator de conversão')),
                ('ignorado', models.BooleanField(db_index=True, default=False, verbose_name='Ignorado (fora do KPI)')),
                ('item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='codigos', to='kpi.hieritem')),
            ],
            options={'verbose_name': 'Código de insumo', 'verbose_name_plural': 'Códigos de insumo', 'ordering': ['codigo']},
        ),
        migrations.CreateModel(
            name='HierMovimento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.DateField(db_index=True)),
                ('quantidade', models.DecimalField(decimal_places=3, max_digits=14)),
                ('tipo', models.CharField(help_text='UTILIZACOES, PERDAS, DEVOLUCAO...', max_length=20, verbose_name='Tipo de movimento')),
                ('origem', models.CharField(blank=True, max_length=30)),
                ('identif', models.BigIntegerField(blank=True, null=True, verbose_name='Identificador do movimento')),
                ('codigo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimentos', to='kpi.hiercodigo')),
            ],
            options={
                'verbose_name': 'Movimento de insumo',
                'verbose_name_plural': 'Movimentos de insumo',
                'ordering': ['-data', 'codigo'],
                'indexes': [models.Index(fields=['codigo', 'data'], name='kpi_hiermov_codigo_data_idx')],
            },
        ),
    ]
