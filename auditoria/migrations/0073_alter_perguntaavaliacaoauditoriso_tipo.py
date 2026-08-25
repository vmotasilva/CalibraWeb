from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0072_perguntaavaliacaoauditoriso_opcoes_lista'),
    ]

    operations = [
        migrations.AlterField(
            model_name='perguntaavaliacaoauditoriso',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('ESTRELAS_1_5', 'Classificação por Estrelas (1 a 5)'),
                    ('TEXTO_LIVRE', 'Caixa de Texto / Resposta Dissertativa'),
                    ('SELECAO_LISTA', 'Lista de Seleção (Múltipla Escolha / Opções)'),
                    ('AGRUPAMENTO_ESCALA', 'Agrupamento (Supera, Atende, Não Atende, Não se Aplica)')
                ],
                default='ESTRELAS_1_5',
                max_length=30,
                verbose_name='Tipo de Resposta'
            ),
        ),
    ]
