from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0071_perguntaavaliacaoauditoriso_and_respostaitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='perguntaavaliacaoauditoriso',
            name='opcoes_lista',
            field=models.TextField(blank=True, default='', verbose_name='Opções da Lista (uma por linha ou separadas por vírgula)'),
        ),
        migrations.AlterField(
            model_name='perguntaavaliacaoauditoriso',
            name='tipo',
            field=models.CharField(choices=[('ESTRELAS_1_5', 'Classificação por Estrelas (1 a 5)'), ('TEXTO_LIVRE', 'Caixa de Texto / Resposta Dissertativa'), ('SELECAO_LISTA', 'Lista de Seleção (Múltipla Escolha / Opções)')], default='ESTRELAS_1_5', max_length=20, verbose_name='Tipo de Resposta'),
        ),
    ]
