from django.contrib import admin
from django.utils.html import format_html
from datetime import date, timedelta
from .models import (
    Colaborador, Instrumento, TipoMedicao, HistoricoCalibracao, 
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento, 
    Setor, CentroCusto, HierarquiaSetor,
    Documento, RegistroTreinamento
)

# ==============================================================================
# FILTROS PERSONALIZADOS (LÓGICA INTELIGENTE)
# ==============================================================================

class SetorPorGrupoFilter(admin.SimpleListFilter):
    """
    Filtra os Setores baseando-se no Grupo selecionado.
    Se o usuário filtrar por 'MANUTENCAO', só aparecem setores onde
    existem colaboradores da manutenção.
    """
    title = 'Setor (Dinâmico)'
    parameter_name = 'setor_id' # Filtraremos pelo ID do setor

    def lookups(self, request, model_admin):
        # 1. Verifica se já existe um filtro de GRUPO aplicado na URL
        grupo_selecionado = request.GET.get('grupo')

        if grupo_selecionado:
            # Se tem grupo, busca apenas setores usados por colaboradores desse grupo
            # distinct() evita repetição
            setores = (
                Setor.objects
                .filter(colaborador__grupo=grupo_selecionado)
                .distinct()
                .order_by('nome')
            )
        else:
            # Se não tem grupo, mostra apenas setores que têm ALGUM colaborador (evita setores vazios)
            setores = (
                Setor.objects
                .filter(colaborador__isnull=False)
                .distinct()
                .order_by('nome')
            )

        # Retorna lista de tuplas (ID, Nome) para o Django montar o menu
        return [(s.id, s.nome) for s in setores]

    def queryset(self, request, queryset):
        # Aplica o filtro se o usuário selecionar uma opção
        if self.value():
            return queryset.filter(setor__id=self.value())
        return queryset


# ==============================================================================
# 0. SETORES E CENTROS DE CUSTO
# ==============================================================================
class CentroCustoInline(admin.TabularInline):
    model = CentroCusto
    extra = 1 

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'listar_ccs', 'responsavel')
    search_fields = ('nome',)
    inlines = [CentroCustoInline] 

    def listar_ccs(self, obj):
        return ", ".join([cc.codigo for cc in obj.centros_custo.all()])
    listar_ccs.short_description = 'Centros de Custo'

@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin):
    search_fields = ('codigo', 'descricao', 'setor__nome')
    list_display = ('codigo', 'descricao', 'setor')

# ==============================================================================
# 1. COLABORADORES (RH)
# ==============================================================================
class TreinamentoInline(admin.TabularInline):
    model = RegistroTreinamento
    extra = 0
    fields = ('documento', 'revisao_treinada', 'data_treinamento', 'status_visual')
    readonly_fields = ('status_visual',)

    def status_visual(self, obj):
        if obj.status_treinamento == "VIGENTE":
            return format_html('<span style="color: green; font-weight: bold;">VIGENTE</span>')
        return format_html('<span style="color: red; font-weight: bold;">PENDENTE</span>')
    status_visual.short_description = "Status"

@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'nome_completo', 'cargo', 'grupo', 'setor', 'is_active')
    search_fields = ('matricula', 'nome_completo', 'cargo')
    
    # <--- MUDANÇA AQUI: Usamos a classe SetorPorGrupoFilter no lugar de 'setor'
    # A ordem importa: Grupo deve vir antes para o usuário filtrar primeiro
    list_filter = ('is_active', 'grupo', SetorPorGrupoFilter, 'turno')
    
    autocomplete_fields = ['setor', 'centro_custo'] 
    inlines = [TreinamentoInline] 

    fieldsets = (
        ("Dados de Login", {'fields': ('username', 'matricula', 'is_active', 'is_admin')}),
        ("Dados Pessoais", {'fields': ('nome_completo', 'cargo', 'grupo', 'setor', 'centro_custo', 'turno')}),
    )

@admin.register(HierarquiaSetor)
class HierarquiaSetorAdmin(admin.ModelAdmin):
    list_display = ('setor', 'turno', 'lider', 'supervisor', 'gerente')
    list_filter = ('setor', 'turno')
    autocomplete_fields = ['lider', 'supervisor', 'gerente', 'diretor', 'setor']

# ==============================================================================
# 2. INSTRUMENTOS (METROLOGIA)
# ==============================================================================
class TipoMedicaoInline(admin.TabularInline):
    model = TipoMedicao
    extra = 0
    fields = ('grandeza', 'faixa', 'resolucao', 'periodicidade_meses', 'data_ultima_calibracao', 'data_proxima_calibracao')
    readonly_fields = ('data_proxima_calibracao',)

@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ('tag', 'descricao', 'marca', 'get_setor_nome', 'status')
    search_fields = ('tag', 'descricao', 'serie', 'marca', 'modelo', 'setor__nome')
    list_filter = ('status', 'setor') 
    inlines = [TipoMedicaoInline]
    autocomplete_fields = ['setor'] 

    def get_setor_nome(self, obj):
        return obj.setor.nome if obj.setor else "-"
    get_setor_nome.short_description = 'Setor'

# ==============================================================================
# 3. MONITORAMENTO DE VENCIMENTOS
# ==============================================================================
def status_vencimento(obj):
    if not obj.data_proxima_calibracao: return "Sem Data"
    if obj.data_proxima_calibracao < date.today():
        return format_html('<span style="color: red; font-weight: bold;">VENCIDO</span>')
    if obj.data_proxima_calibracao < date.today() + timedelta(days=30):
        return format_html('<span style="color: orange; font-weight: bold;">VENCE EM BREVE</span>')
    return format_html('<span style="color: green;">VIGENTE</span>')
status_vencimento.short_description = 'Situação'

@admin.register(TipoMedicao)
class PainelAcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ('instrumento_tag', 'get_setor', 'grandeza', 'data_ultima_calibracao', 'data_proxima_calibracao', status_vencimento)
    search_fields = ('instrumento__tag', 'grandeza', 'instrumento__marca', 'instrumento__setor__nome')
    list_filter = ('grandeza', 'periodicidade_meses', 'instrumento__setor')
    ordering = ('data_proxima_calibracao',)
    
    def instrumento_tag(self, obj): return obj.instrumento.tag
    instrumento_tag.short_description = 'Tag'
    def get_setor(self, obj): return obj.instrumento.setor.nome if obj.instrumento.setor else "-"
    get_setor.short_description = 'Setor'

# ==============================================================================
# 4. HISTÓRICO DE CALIBRAÇÃO
# ==============================================================================
@admin.register(HistoricoCalibracao)
class HistoricoAdmin(admin.ModelAdmin):
    list_display = ('data_calibracao', 'instrumento_tag', 'grandeza', 'resultado', 'ver_certificado')
    list_filter = ('resultado', 'data_calibracao')
    
    def instrumento_tag(self, obj): return obj.tipo_medicao.instrumento.tag
    def grandeza(self, obj): return obj.tipo_medicao.grandeza
    def ver_certificado(self, obj):
        if obj.certificado_pdf:
            return format_html("<a href='{}' target='_blank'>PDF</a>", obj.certificado_pdf.url)
        return "-"

# ==============================================================================
# 5. FORNECEDORES E AVALIAÇÃO
# ==============================================================================
class AvaliacaoInline(admin.TabularInline):
    model = AvaliacaoFornecedor
    extra = 0
    fields = ('data_avaliacao', 'nota_tecnica', 'nota_pontualidade', 'nota_atendimento', 'observacao')
    readonly_fields = ('data_avaliacao',)

@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'contato', 'telefone', 'status_badge', 'nota_media_colorida')
    list_filter = ('status',)
    search_fields = ('nome_fantasia', 'cnpj')
    inlines = [AvaliacaoInline]

    def status_badge(self, obj):
        color = "green" if obj.status == 'HOMOLOGADO' else ("red" if obj.status == 'BLOQUEADO' else "orange")
        return format_html(f'<span style="color: {color}; font-weight: bold;">{obj.get_status_display()}</span>')
    status_badge.short_description = 'Status'

    def nota_media_colorida(self, obj):
        val = obj.nota_media
        color = "green" if val >= 7 else ("orange" if val >= 5 else "red")
        return format_html(f'<span style="font-size: 14px; color: {color}; font-weight: bold;">★ {val}</span>')
    nota_media_colorida.short_description = 'Nota Média'

# ==============================================================================
# 6. COTAÇÕES
# ==============================================================================
class OrcamentoInline(admin.TabularInline):
    model = Orcamento
    extra = 1

@admin.register(ProcessoCotacao)
class ProcessoCotacaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_abertura', 'prazo_limite', 'contar_propostas', 'status')
    list_filter = ('status',)
    filter_horizontal = ('instrumentos',)
    inlines = [OrcamentoInline]
    
    def contar_propostas(self, obj): return obj.orcamentos.count()
    contar_propostas.short_description = 'Propostas'

# ==============================================================================
# 7. DOCUMENTOS E TREINAMENTOS (GED)
# ==============================================================================
@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'revisao_atual', 'data_revisao', 'setor')
    search_fields = ('codigo', 'titulo')
    list_filter = ('setor',)

@admin.register(RegistroTreinamento)
class RegistroTreinamentoAdmin(admin.ModelAdmin):
    list_display = ('colaborador', 'documento_info', 'revisao_treinada', 'data_treinamento', 'status_visual')
    search_fields = ('colaborador__nome_completo', 'documento__codigo')
    list_filter = ('documento__codigo', 'revisao_treinada')
    autocomplete_fields = ['colaborador', 'documento']

    def documento_info(self, obj):
        return f"{obj.documento.codigo} (Rev. Atual: {obj.documento.revisao_atual})"
    documento_info.short_description = "Documento"

    def status_visual(self, obj):
        if obj.status_treinamento == "VIGENTE":
            return format_html('<span style="color: green; font-weight: bold;">VIGENTE</span>')
        return format_html('<span style="color: red; font-weight: bold;">PENDENTE</span>')
    status_visual.short_description = "Situação"