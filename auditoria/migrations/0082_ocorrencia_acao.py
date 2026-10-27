from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0081_ocorrencia_responsaveis_prazo"),
    ]

    operations = [
        migrations.AddField(
            model_name="comentariorespostaauditoria",
            name="acao",
            field=models.TextField(blank=True, default="", verbose_name="Ação a ser realizada"),
        ),
    ]
