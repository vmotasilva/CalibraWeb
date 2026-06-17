from django.contrib import admin
from boards.models import Board, BoardColumn, Card, ChecklistItem, CardComment, BoardActivity, BoardLabel

class BoardColumnInline(admin.TabularInline):
    model = BoardColumn
    extra = 1

@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('nome', 'criado_por', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'descricao')
    filter_horizontal = ('membros',)
    inlines = [BoardColumnInline]

class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1

class CardCommentInline(admin.TabularInline):
    model = CardComment
    extra = 0

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'coluna', 'get_responsaveis', 'prioridade', 'data_entrega', 'ordem')
    list_filter = ('prioridade', 'coluna__quadro', 'data_entrega')
    search_fields = ('titulo', 'descricao')
    filter_horizontal = ('responsaveis',)
    inlines = [ChecklistItemInline, CardCommentInline]

    def get_responsaveis(self, obj):
        return ", ".join([r.nome_completo for r in obj.responsaveis.all()])
    get_responsaveis.short_description = "Responsáveis"


@admin.register(BoardColumn)
class BoardColumnAdmin(admin.ModelAdmin):
    list_display = ('nome', 'quadro', 'ordem')
    list_filter = ('quadro',)
    search_fields = ('nome',)

@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'cartao', 'concluido')
    list_filter = ('concluido', 'cartao__coluna__quadro')
    search_fields = ('descricao',)

@admin.register(CardComment)
class CardCommentAdmin(admin.ModelAdmin):
    list_display = ('autor', 'cartao', 'criado_em')
    list_filter = ('cartao__coluna__quadro',)
    search_fields = ('texto',)

@admin.register(BoardActivity)
class BoardActivityAdmin(admin.ModelAdmin):
    list_display = ('quadro', 'colaborador', 'descricao', 'criado_em')
    list_filter = ('quadro',)
    search_fields = ('descricao',)


@admin.register(BoardLabel)
class BoardLabelAdmin(admin.ModelAdmin):
    list_display = ('nome', 'quadro', 'cor')
    list_filter = ('quadro',)
    search_fields = ('nome',)

