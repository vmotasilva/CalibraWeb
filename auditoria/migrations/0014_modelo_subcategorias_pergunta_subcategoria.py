from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0013_perguntaauditoria_opcoes_resposta"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeloauditoria",
            name="subcategorias",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Uma sub-categoria por linha (ex.: Segurança, Qualidade, 5S).",
                verbose_name="Sub-categorias",
            ),
        ),
        migrations.AddField(
            model_name="perguntaauditoria",
            name="subcategoria",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Opcional. Deve existir nas sub-categorias do modelo (quando definidas).",
                max_length=80,
                verbose_name="Sub-categoria",
            ),
        ),
    ]
