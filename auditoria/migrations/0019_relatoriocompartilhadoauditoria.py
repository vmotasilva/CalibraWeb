from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0018_comentarioresposta_data_referencia_sem_registro"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RelatorioCompartilhadoAuditoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, default="", max_length=64, unique=True)),
                ("inicio", models.DateField(blank=True, null=True, verbose_name="Período Inicial")),
                ("fim", models.DateField(blank=True, null=True, verbose_name="Período Final")),
                ("subcategoria", models.CharField(blank=True, default="", max_length=80, verbose_name="Sub-categoria")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "expira_em",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Expira em",
                    ),
                ),
                ("primeiro_acesso_em", models.DateTimeField(blank=True, null=True, verbose_name="Primeiro acesso")),
                (
                    "recebido_em",
                    models.DateTimeField(blank=True, null=True, verbose_name="Comprovante de recebimento"),
                ),
                ("recebido_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP de recebimento")),
                ("recebido_user_agent", models.CharField(blank=True, default="", max_length=255, verbose_name="Navegador")),
                ("ativo", models.BooleanField(default=True)),
                (
                    "destinatario",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="auditoria_relatorios_recebidos",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Destinatário",
                    ),
                ),
                (
                    "modelo",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="relatorios_compartilhados",
                        to="auditoria.modeloauditoria",
                        verbose_name="Modelo",
                    ),
                ),
                (
                    "remetente",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="auditoria_relatorios_enviados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Remetente",
                    ),
                ),
            ],
            options={
                "verbose_name": "Relatório Compartilhado (Auditoria)",
                "verbose_name_plural": "Relatórios Compartilhados (Auditoria)",
                "ordering": ["-criado_em", "-id"],
            },
        )
    ]
