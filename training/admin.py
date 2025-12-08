from django.contrib import admin
from .models import Area, Procedimento, ProcedimentoRevisao, PacoteTreinamento, RegistroTreinamento

# Register your models here.
admin.site.register(Area)
admin.site.register(Procedimento)
admin.site.register(ProcedimentoRevisao)
admin.site.register(PacoteTreinamento)
admin.site.register(RegistroTreinamento)
