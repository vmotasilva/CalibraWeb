from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0084_auditores_auditados"),
    ]

    operations = [
        migrations.AddField(
            model_name="blocomodeloiso",
            name="dia",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Dia da auditoria",
                help_text="1 = primeiro dia útil da auditoria, 2 = segundo... Vazio = segue o fluxo do bloco anterior.",
            ),
        ),
        migrations.AddField(
            model_name="blocomodeloiso",
            name="duracao_min",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Duração (min)",
                help_text="Vazio = usa a duração padrão informada no planejamento.",
            ),
        ),
    ]
