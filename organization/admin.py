from django.contrib import admin
from .models import Setor, CentroCusto, HierarquiaSetor


class SetorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'responsavel']
    search_fields = ['nome', 'responsavel']
    ordering = ['nome']


class CentroCustoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'descricao', 'setor']
    search_fields = ['codigo', 'descricao']
    list_filter = ['setor']
    list_select_related = ['setor']  # FK optimization
    ordering = ['setor', 'codigo']


class HierarquiaSetorAdmin(admin.ModelAdmin):
    list_display = ['setor', 'turno', 'lider', 'supervisor', 'gerente', 'diretor']
    search_fields = ['setor__nome']
    list_filter = ['turno', 'setor']
    list_select_related = ['setor', 'lider', 'supervisor', 'gerente', 'diretor']  # FK optimization
    ordering = ['setor', 'turno']


admin.site.register(Setor, SetorAdmin)
admin.site.register(CentroCusto, CentroCustoAdmin)
admin.site.register(HierarquiaSetor, HierarquiaSetorAdmin)
