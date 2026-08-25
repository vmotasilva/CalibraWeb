import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auditoria", "0068_auditoriaiso_municipio"),
    ]

    operations = [
        # 1. Adicionar campos de CAPA em SolicitacaoEvidenciaIso
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_status",
            field=models.CharField(
                choices=[
                    ("PENDENTE", "Pendente de Plano"),
                    ("AGUARDANDO_REVISAO", "Aguardando Revisão"),
                    ("APROVADO", "Plano Aprovado"),
                    ("REJEITADO", "Plano Rejeitado"),
                ],
                default="PENDENTE",
                max_length=20,
                verbose_name="Status do Plano de Ação (CAPA)",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_causa_raiz",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Análise de Causa Raiz",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_acao_corretiva",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Ação Corretiva / Preventiva",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_responsavel",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Responsável pela Ação",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_prazo",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Prazo Estimado",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_respondido_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Respondido em",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_respondido_por_nome",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Nome do Respondente / Gestor",
            ),
        ),
        migrations.AddField(
            model_name="solicitacaoevidenciaiso",
            name="capa_parecer_auditor",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Parecer / Feedback do Auditor",
            ),
        ),

        # 2. Criar modelo EvidenciaPlanoAcaoIso
        migrations.CreateModel(
            name="EvidenciaPlanoAcaoIso",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="auditoria/capa/%Y/%m/",
                        verbose_name="Arquivo Comprovante",
                    ),
                ),
                (
                    "arquivo_base64",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Backup para persistência garantida",
                        verbose_name="Dados Base64",
                    ),
                ),
                (
                    "nome_arquivo",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Nome do Arquivo",
                    ),
                ),
                (
                    "tipo_arquivo",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=50,
                        verbose_name="Tipo MIME / Extensão",
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "solicitacao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidencias_capa",
                        to="auditoria.solicitacaoevidenciaiso",
                        verbose_name="Solicitação / Não Conformidade",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evidência do Plano de Ação",
                "verbose_name_plural": "Evidências do Plano de Ação",
                "ordering": ["criado_em"],
            },
        ),

        # 3. Criar modelo PlanoAcaoMagicLink
        migrations.CreateModel(
            name="PlanoAcaoMagicLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "token",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        unique=True,
                        verbose_name="Token de Acesso",
                    ),
                ),
                (
                    "dias_validade",
                    models.PositiveIntegerField(
                        default=15,
                        verbose_name="Validade em Dias",
                    ),
                ),
                (
                    "expira_em",
                    models.DateTimeField(verbose_name="Data de Expiração"),
                ),
                (
                    "incluir_om",
                    models.BooleanField(
                        default=False,
                        verbose_name="Incluir OMs no Escopo",
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "ultimo_acesso_em",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Último Acesso",
                    ),
                ),
                (
                    "ativo",
                    models.BooleanField(
                        default=True,
                        verbose_name="Link Ativo",
                    ),
                ),
                (
                    "agenda",
                    models.ForeignKey(
                        blank=True,
                        help_text="Se vazio, o link dá acesso a todas as Não Conformidades da auditoria.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="magic_links_capa",
                        to="auditoria.agendaauditoriaiso",
                        verbose_name="Setor / Bloco Filtrado",
                    ),
                ),
                (
                    "auditoria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="magic_links_capa",
                        to="auditoria.auditoriaiso",
                        verbose_name="Auditoria de Origem",
                    ),
                ),
                (
                    "criado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Criado por",
                    ),
                ),
            ],
            options={
                "verbose_name": "Magic Link de Plano de Ação",
                "verbose_name_plural": "Magic Links de Planos de Ação",
                "ordering": ["-criado_em"],
            },
        ),
    ]
