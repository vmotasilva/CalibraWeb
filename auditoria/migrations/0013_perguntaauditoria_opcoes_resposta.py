from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0012_perguntaauditoria_aplicar_no_grid"),
    ]

    operations = [
        migrations.AddField(
            model_name="perguntaauditoria",
            name="opcoes_resposta",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Apenas para tipo 'Lista (opções)'. Use uma opção por linha.",
                verbose_name="Opções de resposta",
            ),
        ),
    ]
