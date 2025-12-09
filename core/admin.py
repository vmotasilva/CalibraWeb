from django.contrib import admin
from .models import UnidadeMedida


class UnidadeMedidaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome']
    ordering = ['nome']


admin.site.register(UnidadeMedida, UnidadeMedidaAdmin)
