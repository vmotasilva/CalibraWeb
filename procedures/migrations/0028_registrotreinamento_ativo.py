# Generated migration for adding ativo field to RegistroTreinamento

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("procedures", "0027_update_criticidade_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="registrotreinamento",
            name="ativo",
            field=models.BooleanField(
                default=True,
                help_text="Define se o grupo/sub-grupo se aplica ao colaborador",
                verbose_name="Ativo",
            ),
        ),
    ]
