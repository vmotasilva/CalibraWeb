from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0017_alter_comentariorespostaauditoria_unique_together"),
    ]

    operations = [
        migrations.AlterField(
            model_name="comentariorespostaauditoria",
            name="registro",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="comentarios_resposta",
                to="auditoria.registroauditoria",
                verbose_name="Registro",
            ),
        ),
        migrations.AddField(
            model_name="comentariorespostaauditoria",
            name="data_referencia",
            field=models.DateField(
                blank=True,
                db_index=True,
                help_text="Data usada para vincular o comentário ao período/auditoria, inclusive quando ainda não há registro.",
                null=True,
                verbose_name="Data de Referência",
            ),
        ),
    ]
