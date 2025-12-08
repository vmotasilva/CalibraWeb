from django.contrib import admin
from .models import Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento

# Register your models here.
admin.site.register(Fornecedor)
admin.site.register(AvaliacaoFornecedor)
admin.site.register(ProcessoCotacao)
admin.site.register(Orcamento)
