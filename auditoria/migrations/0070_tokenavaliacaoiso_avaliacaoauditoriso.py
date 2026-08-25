# Generated manually for AvaliacaoAuditorIso and TokenAvaliacaoIso

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0069_planoacaomagiclink_evidenciaplanoacaoiso_and_capa_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TokenAvaliacaoIso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='Token de Acesso')),
                ('dias_validade', models.PositiveIntegerField(default=7, verbose_name='Validade em Dias')),
                ('expira_em', models.DateTimeField(verbose_name='Data de Expiração')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('ultimo_acesso_em', models.DateTimeField(blank=True, null=True, verbose_name='Último Acesso')),
                ('ativo', models.BooleanField(default=True, verbose_name='Link Ativo')),
                ('total_respostas', models.PositiveIntegerField(default=0, verbose_name='Total de Respostas Coletadas')),
                ('auditoria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tokens_avaliacao', to='auditoria.auditoriaiso', verbose_name='Auditoria de Origem')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
            ],
            options={
                'verbose_name': 'Token de Avaliação de Auditoria',
                'verbose_name_plural': 'Tokens de Avaliação de Auditoria',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.CreateModel(
            name='AvaliacaoAuditorIso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nota_pontualidade', models.PositiveSmallIntegerField(help_text='Nota de 1 a 5 estrelas', verbose_name='Pontualidade e Cumprimento da Agenda')),
                ('nota_clareza', models.PositiveSmallIntegerField(help_text='Nota de 1 a 5 estrelas', verbose_name='Clareza e Comunicação')),
                ('nota_cordialidade', models.PositiveSmallIntegerField(help_text='Nota de 1 a 5 estrelas', verbose_name='Cordialidade, Postura e Empatia')),
                ('pontos_fortes', models.TextField(blank=True, default='', verbose_name='Pontos Fortes do Auditor')),
                ('oportunidades_melhoria', models.TextField(blank=True, default='', verbose_name='Oportunidades de Melhoria')),
                ('setor_avaliador', models.CharField(blank=True, default='', max_length=150, verbose_name='Setor do Avaliador (Ex: Produção, EHS, Qualidade)')),
                ('nome_avaliador', models.CharField(blank=True, default='', max_length=150, verbose_name='Nome do Avaliador (Opcional - Anônimo por padrão)')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Data da Avaliação')),
                ('auditoria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='avaliacoes_auditor', to='auditoria.auditoriaiso', verbose_name='Auditoria')),
                ('token_origem', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='avaliacoes_recebidas', to='auditoria.tokenavaliacaoiso', verbose_name='Token Utilizado')),
            ],
            options={
                'verbose_name': 'Avaliação de Auditor ISO',
                'verbose_name_plural': 'Avaliações de Auditores ISO',
                'ordering': ['-criado_em'],
            },
        ),
    ]
