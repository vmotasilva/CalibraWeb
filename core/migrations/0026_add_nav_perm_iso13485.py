from django.db import migrations

PERMISSOES_ISO = [
    # Blocos
    ("nav_auditoria_iso_bloco", "NAV: Auditoria / Bloco ISO 13485 - Auditorias & Ferramentas"),
    ("nav_auditoria_iso_setup_bloco", "NAV: Auditoria / Bloco ISO 13485 - Setup & Cadastros"),

    # Funções - Operação & Ferramentas
    ("nav_auditoria_iso_lista", "NAV: Auditoria / ISO 13485 - Modo Entrevista (Lista)"),
    ("nav_auditoria_iso_entrevista", "NAV: Auditoria / ISO 13485 - Execução da Entrevista"),
    ("nav_auditoria_iso_revisao", "NAV: Auditoria / ISO 13485 - Painel de Revisão"),
    ("nav_auditoria_iso_matriz", "NAV: Auditoria / ISO 13485 - Matriz de Correlação"),
    ("nav_auditoria_iso_cronograma", "NAV: Auditoria / ISO 13485 - Cronograma & Horários"),
    ("nav_auditoria_iso_sintese", "NAV: Auditoria / ISO 13485 - Síntese da Auditoria"),
    ("nav_auditoria_iso_fechamento", "NAV: Auditoria / ISO 13485 - Apresentação de Fechamento"),
    ("nav_auditoria_iso_amostras", "NAV: Auditoria / ISO 13485 - Gestão de Amostras"),
    ("nav_auditoria_iso_capa", "NAV: Auditoria / ISO 13485 - Planos de Ação (CAPA)"),
    ("nav_auditoria_iso_avaliacao", "NAV: Auditoria / ISO 13485 - Avaliação do Auditor"),
    ("nav_auditoria_iso_analytics", "NAV: Auditoria / ISO 13485 - Analytics Global"),
    ("nav_auditoria_iso_export", "NAV: Auditoria / ISO 13485 - Exportar Relatórios (Excel/Word)"),

    # Funções - Setup & Cadastros
    ("nav_auditoria_iso_setup", "NAV: Auditoria / ISO 13485 - Painel de Setup"),
    ("nav_auditoria_iso_normas", "NAV: Auditoria / ISO 13485 - Normas ISO e Requisitos"),
    ("nav_auditoria_iso_itens", "NAV: Auditoria / ISO 13485 - Itens da Norma"),
    ("nav_auditoria_iso_perguntas", "NAV: Auditoria / ISO 13485 - Banco de Perguntas ISO"),
    ("nav_auditoria_iso_modelos", "NAV: Auditoria / ISO 13485 - Modelos e Blocos ISO"),
    ("nav_auditoria_iso_agendas", "NAV: Auditoria / ISO 13485 - Planejamento e Agendas ISO"),
]


def create_iso_permissions(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    content_type, _ = ContentType.objects.get_or_create(
        app_label='core',
        model='navigationpermission',
    )

    for codename, name in PERMISSOES_ISO:
        Permission.objects.update_or_create(
            content_type=content_type,
            codename=codename,
            defaults={'name': name},
        )


def remove_iso_permissions(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    codenames = [c for c, _ in PERMISSOES_ISO]
    Permission.objects.filter(
        content_type__app_label='core',
        codename__in=codenames,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_add_nav_perm_registrar_ferias_todos'),
    ]

    operations = [
        migrations.RunPython(create_iso_permissions, remove_iso_permissions),
    ]
