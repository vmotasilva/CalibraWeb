from django.contrib import admin
from .models import DocumentoGerado, ConfiguracaoCarimbo

# Register your models here.
admin.site.register(DocumentoGerado)
admin.site.register(ConfiguracaoCarimbo)
