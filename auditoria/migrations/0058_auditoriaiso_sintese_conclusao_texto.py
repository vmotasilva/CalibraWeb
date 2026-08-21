from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0057_imagemsolicitacaoiso"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditoriaiso",
            name="sintese",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Síntese executiva formatada em HTML/WYSIWYG com tabelas e imagens",
                verbose_name="Síntese da Auditoria",
            ),
        ),
        migrations.AddField(
            model_name="auditoriaiso",
            name="conclusao_texto",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Conclusão / Parecer Final da Auditoria",
            ),
        ),
    ]
