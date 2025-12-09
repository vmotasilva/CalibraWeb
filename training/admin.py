from django.contrib import admin
from .models import Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento


class AreaAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']
    ordering = ['nome']


class ProcedimentoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'numero_revisao', 'ultima_revisao']
    search_fields = ['codigo', 'nome']
    list_filter = ['ultima_revisao']
    ordering = ['codigo']


class ProcedimentoRevisaoAdmin(admin.ModelAdmin):
    list_display = ['procedimento', 'revisao', 'data_revisao']
    search_fields = ['procedimento__nome']
    list_filter = ['data_revisao']
    list_select_related = ['procedimento', 'elaborador', 'revisor', 'aprovador']  # FK optimization
    ordering = ['-data_revisao']


class PacoteTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome', 'descricao']
    filter_horizontal = ['procedimentos']
    list_prefetch_related = ['colaboradores', 'procedimentos']  # M2M optimization
    ordering = ['nome']


class RegistroTreinamentoAdmin(admin.ModelAdmin):
    list_display = ['colaborador', 'procedimento', 'data_treinamento']
    search_fields = ['colaborador__nome_completo', 'procedimento__nome']
    list_filter = ['data_treinamento']
    list_select_related = ['colaborador', 'procedimento', 'revisor_qualidade']  # FK optimization
    ordering = ['-data_treinamento']


admin.site.register(Area, AreaAdmin)
admin.site.register(Procedimento, ProcedimentoAdmin)
admin.site.register(ProcedimentoRevisao, ProcedimentoRevisaoAdmin)
admin.site.register(PacoteTreinamento, PacoteTreinamentoAdmin)
admin.site.register(RegistroTreinamento, RegistroTreinamentoAdmin)
