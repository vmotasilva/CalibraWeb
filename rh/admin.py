from django.contrib import admin
from .models import Colaborador, HierarquiaSetor, Ferias, Ocorrencia, DocumentoPessoal

# Register your models here.
admin.site.register(Colaborador)
admin.site.register(HierarquiaSetor)
admin.site.register(Ferias)
admin.site.register(Ocorrencia)
admin.site.register(DocumentoPessoal)
