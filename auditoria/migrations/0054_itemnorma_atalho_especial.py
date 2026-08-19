from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0053_add_obs_classificacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemnorma",
            name="atalho_especial",
            field=models.BooleanField(
                default=False,
                help_text="Permite acesso e criação de solicitações rápidas em qualquer bloco no modo entrevista",
                verbose_name="Atalho Especial (Acesso Rápido)",
            ),
        ),
    ]
