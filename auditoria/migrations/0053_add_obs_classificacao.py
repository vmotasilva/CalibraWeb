# Generated for status OBS (Observacao com Correcao)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0052_regraveredictonorma_and_grau_nc"),
    ]

    operations = [
        migrations.AlterField(
            model_name="respostaentrevistaiso",
            name="classificacao",
            field=models.CharField(
                choices=[
                    ("C", "Conforme"),
                    ("OBS", "Observação com Correção"),
                    ("NC", "Não Conforme"),
                    ("NA", "Não Aplicável"),
                    ("OM", "Oportunidade de Melhoria"),
                    ("P", "Pendente"),
                ],
                default="P",
                max_length=4,
            ),
        ),
        migrations.AlterField(
            model_name="solicitacaoevidenciaiso",
            name="conclusao",
            field=models.CharField(
                choices=[
                    ("C", "Conforme"),
                    ("OBS", "Observação com Correção"),
                    ("NC", "Não Conforme"),
                    ("NA", "Não Aplicável"),
                    ("OM", "Oportunidade de Melhoria"),
                    ("P", "Pendente"),
                ],
                default="P",
                max_length=4,
            ),
        ),
        migrations.AlterField(
            model_name="avaliacaofinalrequisitoiso",
            name="classificacao",
            field=models.CharField(
                choices=[
                    ("C", "Conforme"),
                    ("OBS", "Observação com Correção"),
                    ("NC", "Não Conforme"),
                    ("NA", "Não Aplicável"),
                    ("OM", "Oportunidade de Melhoria"),
                    ("P", "Pendente"),
                ],
                max_length=4,
            ),
        ),
    ]
