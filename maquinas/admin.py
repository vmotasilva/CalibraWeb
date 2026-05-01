from django.contrib import admin

from .models import CategoriaMaquina, Maquina


@admin.register(CategoriaMaquina)
class CategoriaMaquinaAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "descricao")


@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "numero_serie", "fabricante", "setor", "categoria", "status")
    list_filter = ("status", "categoria", "setor")
    search_fields = ("codigo", "numero_serie", "fabricante", "setor__nome", "nome", "descricao")