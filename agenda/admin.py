from django.contrib import admin

from agenda.models import Evento, EventoConclusao, EventoParticipante


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
