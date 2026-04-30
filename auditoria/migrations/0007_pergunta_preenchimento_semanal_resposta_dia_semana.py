from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auditoria", "0006_normalize_tipo_resposta_pergunta"),
    ]

    operations = [
        migrations.AddField(
            model_name="perguntaauditoria",
            name="preenchimento_semanal",
            field=models.CharField(
                choices=[
                    ("UNICO", "Uma resposta (sem detalhar por dia)"),
                    ("POR_DIA", "Responder para cada dia da semana"),
                ],
                default="UNICO",
                help_text="Apenas para modelos com periodicidade semanal.",
                max_length=10,
                verbose_name="Preenchimento (semanal)",
            ),
        ),
        migrations.AddField(
            model_name="respostaauditoria",
            name="dia_semana",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SEGUNDA", "Segunda-feira"),
                    ("TERCA", "Terça-feira"),
                    ("QUARTA", "Quarta-feira"),
                    ("QUINTA", "Quinta-feira"),
                    ("SEXTA", "Sexta-feira"),
                    ("SABADO", "Sábado"),
                    ("DOMINGO", "Domingo"),
                ],
                help_text="Usado quando a pergunta exige resposta por dia (auditoria semanal).",
                max_length=10,
                null=True,
                verbose_name="Dia da Semana",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="respostaauditoria",
            unique_together={("registro", "pergunta", "dia_semana")},
        ),
        migrations.AlterModelOptions(
            name="respostaauditoria",
            options={
                "ordering": ["registro", "pergunta__ordem", "dia_semana", "id"],
                "verbose_name": "Resposta de Auditoria",
                "verbose_name_plural": "Respostas de Auditoria",
            },
        ),
    ]
