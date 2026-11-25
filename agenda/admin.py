from django.contrib import admin

from agenda.models import Checklist, ChecklistItem, Evento, EventoConclusao, EventoParticipante


class ParticipanteInline(admin.TabularInline):
    model = EventoParticipante
    extra = 0


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "escopo", "inicio", "recorrencia", "checklist", "criado_por")
    list_filter = ("escopo", "recorrencia", "checklist")
    search_fields = ("titulo", "descricao")
    inlines = [ParticipanteInline]


admin.site.register(EventoConclusao)


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ("titulo", "criado_por", "atualizado_em")
    search_fields = ("titulo",)
    inlines = [ChecklistItemInline]
