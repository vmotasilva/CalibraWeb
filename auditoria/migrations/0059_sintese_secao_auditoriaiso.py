from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auditoria", "0058_auditoriaiso_sintese_conclusao_texto"),
    ]

    operations = [
        migrations.CreateModel(
            name="SinteseSecaoAuditoriaIso",
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
                    "secao_referencia",
                    models.CharField(
                        max_length=20,
                        verbose_name="Referência da Seção (ex: 4, 5, 7.1)",
                    ),
                ),
                (
                    "secao_titulo",
                    models.CharField(
                        max_length=255,
                        verbose_name="Título da Seção / Área",
                    ),
                ),
                (
                    "conteudo_html",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Síntese da Seção (HTML)",
                    ),
                ),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "atualizado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "auditoria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sinteses_secao",
                        to="auditoria.auditoriaiso",
                    ),
                ),
            ],
            options={
                "verbose_name": "Síntese por Seção da Auditoria",
                "verbose_name_plural": "Sínteses por Seção da Auditoria",
                "ordering": ["secao_referencia"],
                "unique_together": {("auditoria", "secao_referencia")},
            },
        ),
    ]
