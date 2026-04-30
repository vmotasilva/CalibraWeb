from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0011_modeloauditoria_grid_colunas"),
    ]

    operations = [
        migrations.AddField(
            model_name="perguntaauditoria",
            name="aplicar_no_grid",
            field=models.BooleanField(
                default=True,
                help_text="Se marcado, esta pergunta aparece no preenchimento em GRID (quando habilitado no modelo).",
                verbose_name="Aplicar no GRID",
            ),
        ),
    ]
