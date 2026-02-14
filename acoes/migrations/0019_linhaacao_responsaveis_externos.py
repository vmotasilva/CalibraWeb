# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("acoes", "0018_tipo_solucao"),
    ]

    operations = [
        migrations.AddField(
            model_name="linhaacao",
            name="responsaveis_externos",
            field=models.TextField(blank=True, null=True, verbose_name="Responsáveis Externos"),
        ),
    ]
