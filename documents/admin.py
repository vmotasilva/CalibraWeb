from django.contrib import admin
from .models import DocumentoGerado, ConfiguracaoCarimbo
from qms.admin import admin_site

# Register your models here.
admin_site.register(DocumentoGerado)
admin_site.register(ConfiguracaoCarimbo)
