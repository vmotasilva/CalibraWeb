# Generated manually for PerguntaAvaliacaoAuditorIso and RespostaItemAvaliacaoIso

import django.db.models.deletion
from django.db import migrations, models


def criar_perguntas_padrao(apps, schema_editor):
    PerguntaAvaliacao = apps.get_model('auditoria', 'PerguntaAvaliacaoAuditorIso')
    AuditoriaIso = apps.get_model('auditoria', 'AuditoriaIso')

    padroes = [
        {
            'titulo': 'Pontualidade e Cumprimento da Agenda',
            'descricao': 'Organização do tempo, cumprimento dos horários e planejamento das entrevistas.',
            'tipo': 'ESTRELAS_1_5',
            'ordem': 1,
            'obrigatoria': True
        },
        {
            'titulo': 'Clareza e Comunicação',
            'descricao': 'Clareza nas perguntas, explicações dos requisitos normativos e feedback objetivo.',
            'tipo': 'ESTRELAS_1_5',
            'ordem': 2,
            'obrigatoria': True
        },
        {
            'titulo': 'Cordialidade, Postura e Empatia',
            'descricao': 'Postura profissional, respeito com os auditados, escuta ativa e conduta ética.',
            'tipo': 'ESTRELAS_1_5',
            'ordem': 3,
            'obrigatoria': True
        },
        {
            'titulo': 'Pontos Fortes do Auditor',
            'descricao': 'O que o auditor fez bem durante a condução da auditoria?',
            'tipo': 'TEXTO_LIVRE',
            'ordem': 4,
            'obrigatoria': False
        },
        {
            'titulo': 'Oportunidades de Melhoria',
            'descricao': 'O que a equipe auditora pode aprimorar em futuras auditorias?',
            'tipo': 'TEXTO_LIVRE',
            'ordem': 5,
            'obrigatoria': False
        }
    ]

    for p in padroes:
        PerguntaAvaliacao.objects.create(
            auditoria=None,
            norma=None,
            titulo=p['titulo'],
            descricao=p['descricao'],
            tipo=p['tipo'],
            ordem=p['ordem'],
            obrigatoria=p['obrigatoria'],
            ativa=True
        )


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0070_tokenavaliacaoiso_avaliacaoauditoriso'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerguntaAvaliacaoAuditorIso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=255, verbose_name='Título / Critério Avaliado')),
                ('descricao', models.TextField(blank=True, default='', verbose_name='Dica / Explicação do Critério')),
                ('tipo', models.CharField(choices=[('ESTRELAS_1_5', 'Classificação por Estrelas (1 a 5)'), ('TEXTO_LIVRE', 'Caixa de Texto / Resposta Dissertativa')], default='ESTRELAS_1_5', max_length=20, verbose_name='Tipo de Resposta')),
                ('ordem', models.PositiveIntegerField(default=1, verbose_name='Ordem de Exibição')),
                ('obrigatoria', models.BooleanField(default=True, verbose_name='Resposta Obrigatória')),
                ('ativa', models.BooleanField(default=True, verbose_name='Pergunta Ativa')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('auditoria', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='perguntas_avaliacao', to='auditoria.auditoriaiso', verbose_name='Auditoria Específica')),
                ('norma', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='perguntas_avaliacao_padrao', to='auditoria.normaiso', verbose_name='Norma Base')),
            ],
            options={
                'verbose_name': 'Pergunta de Avaliação do Auditor',
                'verbose_name_plural': 'Perguntas de Avaliação do Auditor',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RespostaItemAvaliacaoIso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nota_estrelas', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Nota em Estrelas (1 a 5)')),
                ('texto_resposta', models.TextField(blank=True, default='', verbose_name='Resposta em Texto')),
                ('avaliacao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='respostas_itens', to='auditoria.avaliacaoauditoriso', verbose_name='Avaliação Pai')),
                ('pergunta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='respostas_coletadas', to='auditoria.perguntaavaliacaoauditoriso', verbose_name='Pergunta Avaliada')),
            ],
            options={
                'verbose_name': 'Resposta de Item de Avaliação',
                'verbose_name_plural': 'Respostas de Itens de Avaliação',
            },
        ),
        migrations.RunPython(criar_perguntas_padrao, reverse_code=migrations.RunPython.noop),
    ]
