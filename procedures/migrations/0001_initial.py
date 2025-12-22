# -*- coding: utf-8 -*-
"""
Initial migration for procedures app
Consolidates models from training and procurements
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('rh', '0001_initial'),
        ('metrologia', '0001_initial'),
    ]

    operations = [
        # Procedimentos
        migrations.CreateModel(
            name='Procedimento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(blank=True, max_length=50, null=True, unique=True, verbose_name='Código')),
                ('nome', models.CharField(blank=True, max_length=200, null=True, verbose_name='Nome/Título do Documento')),
                ('descricao', models.TextField(blank=True, null=True, verbose_name='Descrição/Objetivo/Função')),
                ('pasta', models.CharField(blank=True, max_length=200, null=True, verbose_name='Pasta (Local no Qualiex)')),
                ('classificacao', models.CharField(blank=True, max_length=100, null=True, verbose_name='Classificação (Tipo de Procedimento)')),
                ('autor', models.CharField(blank=True, max_length=100, null=True, verbose_name='Autor (Texto Livre)')),
                ('numero_revisao', models.CharField(blank=True, max_length=10, null=True, verbose_name='Número da Revisão')),
                ('ultima_revisao', models.DateField(blank=True, null=True, verbose_name='Última Revisão')),
                ('data_aprovacao', models.DateField(blank=True, null=True, verbose_name='Data de Aprovação')),
                ('proxima_revisao', models.DateField(blank=True, null=True, verbose_name='Próxima Revisão')),
                ('data_validade', models.DateField(blank=True, null=True, verbose_name='Data de Validade')),
                ('documentos_controlados', models.CharField(blank=True, max_length=50, null=True, verbose_name='Documentos Controlados')),
                ('matriz', models.CharField(blank=True, max_length=100, null=True, verbose_name='Matriz')),
                ('sub_area', models.CharField(blank=True, max_length=100, null=True, verbose_name='Sub-Área')),
            ],
            options={
                'verbose_name': 'Procedimento',
                'verbose_name_plural': 'Procedimentos (GED)',
                'ordering': ['codigo'],
            },
        ),
        
        # Área
        migrations.CreateModel(
            name='Area',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True, verbose_name='Nome da Área')),
                ('descricao', models.CharField(blank=True, max_length=200, null=True)),
            ],
            options={
                'verbose_name': 'Área',
                'verbose_name_plural': 'Áreas (Macro)',
                'ordering': ['nome'],
            },
        ),
        
        # PacoteTreinamento
        migrations.CreateModel(
            name='PacoteTreinamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True, verbose_name='Nome do Pacote')),
                ('descricao', models.TextField(blank=True, null=True, verbose_name='Descrição')),
                ('procedimentos', models.ManyToManyField(related_name='pacotes', to='procedures.Procedimento', verbose_name='Procedimentos Incluídos')),
            ],
            options={
                'verbose_name': 'Pacote de Treinamento',
                'verbose_name_plural': 'Pacotes de Treinamento',
            },
        ),
        
        # ProcedimentoRevisao
        migrations.CreateModel(
            name='ProcedimentoRevisao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revisao', models.CharField(max_length=10)),
                ('data_revisao', models.DateField(blank=True, null=True)),
                ('data_aprovacao', models.DateField(blank=True, null=True)),
                ('arquivo_prev', models.FileField(blank=True, null=True, upload_to='procedimentos/rev/', verbose_name='Arquivo Revisão Anterior')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('aprovador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revisoes_aprovadas', to='rh.colaborador')),
                ('elaborador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revisoes_elaboradas', to='rh.colaborador')),
                ('procedimento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico_revisoes', to='procedures.Procedimento')),
                ('revisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revisoes_revisadas', to='rh.colaborador')),
            ],
            options={
                'verbose_name': 'Histórico de Revisão de Procedimento',
                'verbose_name_plural': 'Histórico de Revisões',
                'ordering': ['-criado_em'],
            },
        ),
        
        # RegistroTreinamento
        migrations.CreateModel(
            name='RegistroTreinamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revisao_treinada', models.CharField(max_length=10)),
                ('data_treinamento', models.DateField()),
                ('validade_treinamento', models.DateField(blank=True, null=True)),
                ('observacoes', models.TextField(blank=True, null=True)),
                ('colaborador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='treinamentos', to='rh.colaborador')),
                ('procedimento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registros_treinamento', to='procedures.Procedimento')),
                ('revisor_qualidade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revisoes_qualidade', to='rh.colaborador')),
            ],
            options={
                'verbose_name_plural': 'Matriz de Treinamentos',
                'unique_together': {('colaborador', 'procedimento')},
            },
        ),
        
        # Fornecedor
        migrations.CreateModel(
            name='Fornecedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome_fantasia', models.CharField(max_length=100)),
                ('razao_social', models.CharField(blank=True, max_length=150, null=True)),
                ('cnpj', models.CharField(max_length=20, unique=True)),
                ('contato', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('telefone', models.CharField(max_length=20)),
                ('escopo_servico', models.TextField()),
                ('status', models.CharField(choices=[('HOMOLOGADO', 'Homologado'), ('BLOQUEADO', 'Bloqueado'), ('EM_ANALISE', 'Em Análise')], default='EM_ANALISE', max_length=20)),
                ('nota_media', models.DecimalField(decimal_places=1, default=0.0, max_digits=3)),
            ],
            options={
                'verbose_name_plural': 'Fornecedores',
            },
        ),
        
        # AvaliacaoFornecedor
        migrations.CreateModel(
            name='AvaliacaoFornecedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_avaliacao', models.DateField(auto_now_add=True)),
                ('nota_tecnica', models.IntegerField(default=10)),
                ('nota_pontualidade', models.IntegerField(default=10)),
                ('nota_atendimento', models.IntegerField(default=10)),
                ('observacao', models.TextField(blank=True, null=True)),
                ('avaliador', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='rh.colaborador')),
                ('fornecedor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='avaliacoes', to='procedures.Fornecedor')),
            ],
        ),
        
        # ProcessoCotacao
        migrations.CreateModel(
            name='ProcessoCotacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=100)),
                ('data_abertura', models.DateField(auto_now_add=True)),
                ('prazo_limite', models.DateField()),
                ('status', models.CharField(choices=[('ABERTO', 'Aberto'), ('FECHADO', 'Fechado'), ('CANCELADO', 'Cancelado')], default='ABERTO', max_length=20)),
                ('instrumentos', models.ManyToManyField(to='metrologia.Instrumento')),
                ('responsavel', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='rh.colaborador')),
            ],
            options={
                'verbose_name_plural': 'Processos de Cotação',
            },
        ),
        
        # Orcamento
        migrations.CreateModel(
            name='Orcamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valor_total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('prazo_execucao_dias', models.IntegerField()),
                ('arquivo_proposta', models.FileField(upload_to='orcamentos/')),
                ('vencedor', models.BooleanField(default=False)),
                ('observacoes', models.TextField(blank=True, null=True)),
                ('fornecedor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='procedures.Fornecedor')),
                ('processo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orcamentos', to='procedures.ProcessoCotacao')),
            ],
        ),
    ]
