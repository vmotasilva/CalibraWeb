from django.contrib import admin
from .models import Colaborador, Ferias, Ocorrencia, DocumentoPessoal
from organization.models import HierarquiaSetor

# Register your models here.
admin.site.register(Colaborador)
admin.site.register(HierarquiaSetor)
admin.site.register(Ferias)
admin.site.register(Ocorrencia)
admin.site.register(DocumentoPessoal)
