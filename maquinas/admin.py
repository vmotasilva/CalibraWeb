from django.contrib import admin
from .models import Maquina

@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    list_display = ("nome", "codigo", "status")
    search_fields = ("nome", "codigo")