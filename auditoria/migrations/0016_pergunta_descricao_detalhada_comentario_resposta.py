from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auditoria", "0015_alter_perguntaauditoria_tipo_resposta_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="perguntaauditoria",
            name="descricao_detalhada",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Texto exibido no ícone informativo durante o preenchimento do registro.",
                verbose_name="Descrição detalhada",
            ),
        ),
        migrations.CreateModel(
            name="ComentarioRespostaAuditoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("texto", models.TextField(verbose_name="Comentário")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "autor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="auditoria_comentarios_resposta",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Autor",
                    ),
                ),
                (
                    "pergunta",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comentarios_resposta",
                        to="auditoria.perguntaauditoria",
                        verbose_name="Pergunta",
                    ),
                ),
                (
                    "registro",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comentarios_resposta",
                        to="auditoria.registroauditoria",
                        verbose_name="Registro",
                    ),
                ),
            ],
            options={
                "verbose_name": "Comentário da Resposta (Auditoria)",
                "verbose_name_plural": "Comentários das Respostas (Auditoria)",
                "ordering": ["-atualizado_em", "-id"],
                "unique_together": {("registro", "pergunta")},
            },
        ),
    ]
