from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0010_auditoria_grid"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeloauditoria",
            name="grid_colunas",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Uma coluna por linha (ex.: EQP-001). Se vazio, as colunas serão informadas no registro.",
                verbose_name="Colunas do GRID",
            ),
        ),
    ]
