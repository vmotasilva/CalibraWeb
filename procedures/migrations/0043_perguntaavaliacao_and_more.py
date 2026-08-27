# Generated manually for PerguntaAvaliacao and TemplateDocumentoTreinamento choices

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedures', '0042_templatedocumentotreinamento_arquivo_base64_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templatedocumentotreinamento',
            name='codigo',
            field=models.CharField(help_text='Ex: FOR.033.r07, FOR.133, FOR.141, FOR.142, etc.', max_length=50, verbose_name='Código do Formulário'),
        ),
        migrations.AlterField(
            model_name='templatedocumentotreinamento',
            name='funcao',
            field=models.CharField(choices=[('LISTA_PRESENCA', 'Lista de Presença (FOR.033 - Excel/PDF)'), ('PLANEJAMENTO_MATRIZ', 'Planejamento de Treinamento / Cronograma (FOR.133 - Excel)'), ('AUTO_AVALIACAO', 'Auto-Avaliação de Treinamento Crítico (FOR.141 - Excel)'), ('AVALIACAO_EFICACIA', 'Avaliação de Eficácia de Treinamento (FOR.142 - Excel)'), ('CERTIFICADO', 'Certificado de Conclusão'), ('INTEGRACAO', 'Checklist de Integração'), ('OUTROS', 'Outros Templates e Formulários')], default='LISTA_PRESENCA', max_length=50, verbose_name='Função / Finalidade'),
        ),
        migrations.CreateModel(
            name='PerguntaAvaliacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveSmallIntegerField(default=1, help_text='Número da pergunta (1 a 5)', verbose_name='Ordem / Número da Pergunta')),
                ('enunciado', models.TextField(verbose_name='Pergunta / Critério de Avaliação')),
                ('resposta_esperada', models.TextField(blank=True, null=True, verbose_name='Resposta Esperada / Padrão Técnico')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo?')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('matriz', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='perguntas_avaliacao', to='procedures.matrizhabilidade', verbose_name='Matriz de Habilidade')),
                ('procedimento', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='perguntas_avaliacao', to='procedures.procedimento', verbose_name='Procedimento')),
            ],
            options={
                'verbose_name': 'Pergunta de Avaliação (Treinamento Crítico)',
                'verbose_name_plural': 'Perguntas de Avaliação (Treinamentos Críticos)',
                'ordering': ['procedimento', 'matriz', 'ordem'],
            },
        ),
    ]
