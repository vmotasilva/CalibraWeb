# Fornecedores admin registration
from django.contrib import admin
from .models import Fornecedor, CategoriaDocumento, DocumentoFornecedor, AvaliacaoFornecedor, PerguntaAvaliacao, RespostaAvaliacao, OcorrenciaNota

@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("empresa", "nome_fantasia", "cnpj", "uf", "tipo", "ativo")
    search_fields = ("empresa", "nome_fantasia", "cnpj")
    list_filter = ("tipo", "uf", "ativo")

@admin.register(CategoriaDocumento)
class CategoriaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao")
    search_fields = ("nome",)

@admin.register(DocumentoFornecedor)
class DocumentoFornecedorAdmin(admin.ModelAdmin):
    list_display = ("fornecedor", "categoria", "data_validade")
    search_fields = ("fornecedor__empresa", "categoria__nome")
    list_filter = ("categoria",)

@admin.register(AvaliacaoFornecedor)
class AvaliacaoFornecedorAdmin(admin.ModelAdmin):
    list_display = ("fornecedor", "tipo", "data", "avaliador", "pontuacao_ano", "resultado")
    search_fields = ("fornecedor__empresa", "nota_fiscal")
    list_filter = ("tipo", "data")

@admin.register(PerguntaAvaliacao)
class PerguntaAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("texto", "tipo", "ativo", "ordem")
    list_filter = ("tipo", "ativo")
    ordering = ("tipo", "ordem")

@admin.register(RespostaAvaliacao)
class RespostaAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "pergunta", "resposta")
    list_filter = ("resposta",)

@admin.register(OcorrenciaNota)
class OcorrenciaNotaAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "descricao", "pontuacao_perdida")
    search_fields = ("descricao",)
