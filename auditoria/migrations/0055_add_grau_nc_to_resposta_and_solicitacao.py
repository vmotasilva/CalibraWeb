from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0054_itemnorma_atalho_especial"),
    ]

    operations = [
        migrations.AddField(
            model_name="respostaentrevistaiso",
            name="grau_nc",
            field=models.CharField(
                blank=True,
                choices=[("MENOR", "NC Menor"), ("MAIOR", "NC Maior")],
                max_length=10,
                null=True,
                verbose_name="Grau da Não Conformidade",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="grau_nc",
            field=models.CharField(
                blank=True,
                choices=[("MENOR", "NC Menor"), ("MAIOR", "NC Maior")],
                max_length=10,
                null=True,
                verbose_name="Grau da Não Conformidade",
            ),
        ),
    ]
