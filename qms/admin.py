# ==============================================================================
# QMS ADMIN - PHASE 9 MODULARIZATION
# ==============================================================================
# This admin.py is intentionally minimal
# Only ImportJob is registered here
#
# Other cross-app models are registered in their respective app admin files:
# - metrologia/admin.py: SolicitacaoInstrumento, OcorrenciaInstrumento
# ==============================================================================

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import ImportJob


# --- Customização do AdminSite para Agrupamento ---
class CalibraAdminSite(admin.AdminSite):
    site_header = 'Calibra QMS - Administração'
    site_title = 'Calibra QMS Admin'
    index_title = 'Site administration'

    def get_app_list(self, request):
        # Agrupamento customizado
        app_dict = self._build_app_dict(request)
        # Ordem e títulos customizados
        ordering = [
            ('AUTH', _('Authentication and Authorization'), [
                'User', 'Group',
            ]),
            ('HR', _('HR'), [
                'Colaborador', 'Ferias', 'DocumentoPessoal', 'Ocorrencia', 'Vacation periods', 'Employee documents', 'Employee occurrences', 'Employees',
            ]),
            ('METROLOGY', _('Metrology'), [
                'Instrumento', 'FaixaMedicao', 'CategoriaInstrumento', 'HistoricoCalibracao', 'OrdemCalibracao',
            ]),
            ('GED', _('Procedures & Training'), [
                'Procedimento', 'ProcedimentoRevisao', 'Area', 'RegistroTreinamento', 'PacoteTreinamento',
            ]),
            ('PERIODIC TASKS', _('Periodic Tasks'), [
                'Clocked', 'Crontabs', 'Intervals',
            ]),
            ('SUPPLY', _('Suppliers & Quotes'), [
                'Fornecedor', 'ProcessoCotacao', 'Orcamento',
            ]),
            ('REQUESTS', _('Requests'), [
                'SolicitacaoInstrumento',
            ]),
        ]
        custom_apps = []
        for code, title, models in ordering:
            app_models = []
            for model in models:
                for app in app_dict.values():
                    for m in app['models']:
                        if m['object_name'] == model or m['name'] == model:
                            app_models.append(m)
            if app_models:
                custom_apps.append({'name': title, 'app_label': code, 'models': app_models})
        # Adiciona apps não agrupados
        grouped = set(m['object_name'] for app in custom_apps for m in app['models'])
        for app in app_dict.values():
            extra_models = [m for m in app['models'] if m['object_name'] not in grouped]
            if extra_models:
                custom_apps.append({'name': app['name'], 'app_label': app['app_label'], 'models': extra_models})
        return custom_apps


# Substitui o site padrão
admin_site = CalibraAdminSite(name='calibra_admin')


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'job_type', 'status', 'created_at')
    list_filter = ('status', 'job_type', 'created_at')
    search_fields = ('filename', 'filepath')
    readonly_fields = ('id', 'created_at', 'updated_at')
