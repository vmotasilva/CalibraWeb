# Generated migration to remove unidade_padrao from CategoriaInstrumento

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("metrologia", "0023_faixamedicaopadraocategoria"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="categoriainstrumento",
            name="unidade_padrao",
        ),
    ]
