from django.contrib import admin
from .models import Unidade, Setor, CentroCusto, HierarquiaSetor
from qms.admin import admin_site


class UnidadeAdmin(admin.ModelAdmin):
    list_display = ['nome', 'codigo', 'cnpj', 'cidade', 'estado', 'ativo']
    search_fields = ['nome', 'codigo', 'cnpj', 'cidade']
    list_filter = ['ativo', 'estado']
    ordering = ['nome']


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


admin_site.register(Setor, SetorAdmin)
admin_site.register(CentroCusto, CentroCustoAdmin)
admin_site.register(HierarquiaSetor, HierarquiaSetorAdmin)
