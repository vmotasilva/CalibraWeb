from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0059_sintese_secao_auditoriaiso"),
    ]

    operations = [
        migrations.CreateModel(
            name="PontoForteAuditoriaIso",
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
                    "titulo",
                    models.CharField(
                        max_length=255,
                        verbose_name="Título do Ponto Forte",
                    ),
                ),
                (
                    "descricao",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Descrição / Detalhamento",
                    ),
                ),
                (
                    "icone",
                    models.CharField(
                        default="bi-shield-fill-check",
                        max_length=60,
                        verbose_name="Ícone Bootstrap",
                    ),
                ),
                (
                    "ordem",
                    models.IntegerField(
                        default=0,
                        verbose_name="Ordem de Exibição",
                    ),
                ),
                (
                    "criado_em",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "auditoria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pontos_fortes",
                        to="auditoria.auditoriaiso",
                        verbose_name="Auditoria",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ponto Forte da Auditoria",
                "verbose_name_plural": "Pontos Fortes da Auditoria",
                "ordering": ["ordem", "id"],
            },
        ),
    ]
