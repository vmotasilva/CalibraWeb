import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0056_solicitacaoevidenciaiso_agenda"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImagemSolicitacaoIso",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "arquivo",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="auditoria/solicitacoes/%Y/%m/",
                        verbose_name="Arquivo de Imagem",
                    ),
                ),
                (
                    "arquivo_base64",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Backup base64 para persistência garantida em ambientes serverless",
                        verbose_name="Dados Base64",
                    ),
                ),
                (
                    "nome_arquivo",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Nome do Arquivo",
                    ),
                ),
                (
                    "legenda",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Legenda / Descrição da Evidência",
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "solicitacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="imagens",
                        to="auditoria.solicitacaoevidenciaiso",
                        verbose_name="Solicitação de Evidência",
                    ),
                ),
            ],
            options={
                "verbose_name": "Imagem da Solicitação ISO",
                "verbose_name_plural": "Imagens das Solicitações ISO",
                "ordering": ["criado_em"],
            },
        ),
    ]
