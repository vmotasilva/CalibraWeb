import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Só esquema. A conversão dos dados fica na 0036: no Postgres não se pode criar o índice da FK e alterar
    linhas na mesma transação ("pending trigger events")."""

    dependencies = [
        ('kpi', '0034_hier_item_exibir_un_kg'),
    ]

    operations = [
        migrations.AddField(
            model_name='analiseitem', name='pai',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='filhos', to='kpi.analiseitem'),
        ),
        migrations.AddField(
            model_name='analiseitem', name='texto',
            field=models.TextField(blank=True, verbose_name='Texto da nota'),
        ),
    ]
