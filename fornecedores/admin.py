# Fornecedores admin registration
from django.contrib import admin
from .models import (
    AvaliacaoFornecedor, CategoriaDocumento, DocumentoFornecedor, Fornecedor,
    OcorrenciaNota, PerguntaAvaliacao, RespostaAvaliacao, RespostaMatrizAvaliacao,
)


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
    list_select_related = ("fornecedor", "categoria")


class RespostaAvaliacaoInline(admin.TabularInline):
    model = RespostaAvaliacao
    extra = 0
    raw_id_fields = ("pergunta",)


class RespostaMatrizInline(admin.TabularInline):
    model = RespostaMatrizAvaliacao
    extra = 0


@admin.register(AvaliacaoFornecedor)
class AvaliacaoFornecedorAdmin(admin.ModelAdmin):
    list_display = ("fornecedor", "tipo", "data", "avaliador", "pontuacao_ano", "resultado")
    search_fields = ("fornecedor__empresa", "nota_fiscal")
    list_filter = ("tipo", "data")
    list_select_related = ("fornecedor", "avaliador")
    inlines = [RespostaAvaliacaoInline, RespostaMatrizInline]


@admin.register(PerguntaAvaliacao)
class PerguntaAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("texto", "tipo", "produto_servico", "ativo", "ordem")
    list_filter = ("tipo", "ativo")
    ordering = ("tipo", "ordem")


@admin.register(RespostaAvaliacao)
class RespostaAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "pergunta", "resposta")
    list_filter = ("resposta",)
    list_select_related = ("avaliacao__fornecedor", "pergunta")


@admin.register(OcorrenciaNota)
class OcorrenciaNotaAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "descricao", "pontuacao_perdida")
    search_fields = ("descricao",)
