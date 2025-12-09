from django.contrib import admin
from .models import UnidadeMedida
from qms.admin import admin_site


class UnidadeMedidaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome']
    ordering = ['nome']


admin_site.register(UnidadeMedida, UnidadeMedidaAdmin)
