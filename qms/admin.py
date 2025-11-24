from django.contrib import admin
from django.utils.html import format_html
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from datetime import date

# Importando todos os models (Adicionei SolicitacaoInstrumento e OrdemCalibracao)
from .models import (
    Colaborador, Instrumento, HistoricoCalibracao, 
    Fornecedor, AvaliacaoFornecedor, ProcessoCotacao, Orcamento, 
    Setor, CentroCusto, HierarquiaSetor,
    Procedimento, RegistroTreinamento, Ferias, PacoteTreinamento, DocumentoPessoal,
    UnidadeMedida, CategoriaInstrumento, FaixaMedicao, Padrao,
    # Novos Models:
    Ocorrencia, SolicitacaoInstrumento, OrdemCalibracao
)

# --- INLINES (Tabelas dentro de outras telas) ---

class CentroCustoInline(admin.TabularInline): 
    model = CentroCusto
    extra = 1 

class TreinamentoInline(admin.TabularInline):
    model = RegistroTreinamento
    extra = 0
    readonly_fields = ('status_visual',)
    fields = ('procedimento', 'revisao_treinada', 'data_treinamento', 'status_visual')
    def status_visual(self, obj): 
        return format_html('<span style="color:green">VIGENTE</span>') if obj.status_treinamento == "VIGENTE" else format_html('<span style="color:red">PENDENTE</span>')

class FeriasInline(admin.TabularInline): 
    model = Ferias
    extra = 1

class DocumentoPessoalInline(admin.TabularInline): 
    model = DocumentoPessoal
    extra = 1

# CORREÇÃO: Inlines ligados ao Instrumento, não ao Colaborador
class OcorrenciaInline(admin.TabularInline):
    model = Ocorrencia
    extra = 0
    fields = ('tipo', 'data_ocorrencia', 'usuario_responsavel', 'descricao')
    readonly_fields = ('data_ocorrencia',)

class CalibracaoInline(admin.TabularInline):
    model = OrdemCalibracao
    extra = 0
    fields = ('fornecedor', 'tipo_local', 'status', 'data_prevista', 'data_envio', 'data_retorno')

class FaixaMedicaoInline(admin.TabularInline):
    model = FaixaMedicao
    extra = 1


# --- FILTROS PERSONALIZADOS ---

class SetorPorGrupoFilter(admin.SimpleListFilter):
    title = 'Setor (Dinâmico)'
    parameter_name = 'setor_id'
    def lookups(self, request, model_admin):
        g = request.GET.get('grupo')
        qs = Setor.objects.filter(colaborador__grupo=g).distinct() if g else Setor.objects.filter(colaborador__isnull=False).distinct()
        return [(s.id, s.nome) for s in qs]
    def queryset(self, request, queryset): 
        return queryset.filter(setor__id=self.value()) if self.value() else queryset


# --- CADASTROS PRINCIPAIS (RH / ESTRUTURA) ---

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'listar_ccs', 'responsavel')
    search_fields = ('nome',)
    inlines = [CentroCustoInline] 
    def listar_ccs(self, obj): return ", ".join([c.codigo for c in obj.centros_custo.all()])

@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin): 
    search_fields = ('codigo', 'descricao', 'setor__nome')
    list_display = ('codigo', 'descricao', 'setor')

@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    def get_setor_nome(self, obj): return obj.setor.nome if obj.setor else "-"
    def get_cc_code(self, obj): return obj.centro_custo.codigo if obj.centro_custo else "-"
    
    list_display = ('matricula', 'cpf', 'nome_completo', 'cargo', 'lider', 'grupo', 'get_setor_nome', 'salario', 'em_ferias', 'is_active')
    search_fields = ('matricula', 'cpf', 'nome_completo', 'cargo')
    list_filter = ('is_active', 'em_ferias', 'grupo', SetorPorGrupoFilter, 'turno')
    autocomplete_fields = ['setor', 'centro_custo', 'lider'] 
    filter_horizontal = ('pacotes_treinamento',)
    
    # CORREÇÃO: Removi OcorrenciaInline daqui para não dar erro
    inlines = [FeriasInline, DocumentoPessoalInline, TreinamentoInline]
    
    fieldsets = (
        ("Identificação", {'fields': (('matricula', 'cpf'), 'nome_completo')}),
        ("Lotação e Cargo", {'fields': (('cargo', 'salario'), 'lider', ('grupo', 'turno'), ('setor', 'centro_custo'))}),
        ("Treinamentos", {'fields': ('pacotes_treinamento',)}),
        ("Controle", {'fields': ('is_active', 'em_ferias')})
    )

@admin.register(HierarquiaSetor)
class HierarquiaSetorAdmin(admin.ModelAdmin):
    list_display = ('setor', 'turno', 'lider', 'supervisor', 'gerente')
    list_filter = ('setor', 'turno')
    autocomplete_fields = ['lider', 'supervisor', 'gerente', 'diretor', 'setor']
    actions = ['duplicar_hierarquia']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for c in ['lider', 'supervisor', 'gerente', 'diretor', 'setor']:
            if c in form.base_fields:
                w = form.base_fields[c].widget
                w.can_add_related = False
                w.can_change_related = False
                w.can_delete_related = False
        return form

    @admin.action(description='Duplicar')
    def duplicar_hierarquia(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Selecione UMA", level='warning')
            return
        o = queryset.first()
        base = reverse('admin:qms_hierarquiasetor_add')
        qs = urlencode({
            'setor': o.setor.id,
            'lider': o.lider.id if o.lider else '',
            'supervisor': o.supervisor.id if o.supervisor else '',
            'gerente': o.gerente.id if o.gerente else '',
            'diretor': o.diretor.id if o.diretor else ''
        })
        return redirect(f'{base}?{qs}')


# --- CONFIGURAÇÕES DE METROLOGIA (INSTRUMENTOS) ---

@admin.register(UnidadeMedida)
class UnidadeMedidaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla')
    search_fields = ('nome', 'sigla')

@admin.register(CategoriaInstrumento)
class CategoriaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao')
    search_fields = ('nome',)
    # Removi inlines daqui pois Ocorrência é do Instrumento, não da Categoria

@admin.register(Padrao)
class PadraoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descricao', 'data_validade', 'status_validade', 'ativo')
    search_fields = ('codigo', 'descricao', 'numero_certificado')
    list_filter = ('ativo',)
    
    def status_validade(self, obj):
        if obj.esta_vencido:
            return format_html('<span style="color:red; font-weight:bold;">VENCIDO</span>')
        return format_html('<span style="color:green;">VIGENTE</span>')
    status_validade.short_description = "Validade"

@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ('tag', 'descricao', 'categoria', 'responsavel', 'data_proxima_calibracao', 'ativo')
    search_fields = ('tag', 'codigo', 'descricao', 'modelo', 'serie')
    list_filter = ('categoria', 'ativo', 'setor')
    autocomplete_fields = ['responsavel', 'setor', 'categoria']
    
    # AQUI ESTÁ A CORREÇÃO PRINCIPAL: Inlines movidos para cá
    inlines = [FaixaMedicaoInline, OcorrenciaInline, CalibracaoInline]
    
    fieldsets = (
        ('Identificação', {
            'fields': ('tag', 'codigo', 'descricao', 'fabricante', 'modelo', 'serie', 'categoria')
        }),
        ('Localização e Responsável', {
            'fields': ('setor', 'responsavel', 'localizacao')
        }),
        ('Calibração', {
            'fields': ('frequencia_meses', 'data_ultima_calibracao', 'data_proxima_calibracao', 'ativo')
        }),
    )

@admin.register(HistoricoCalibracao)
class HistoricoCalibracaoAdmin(admin.ModelAdmin):
    list_display = ('instrumento', 'certificado', 'data_calibracao', 'resultado', 'fornecedor', 'tem_selo_rbc')
    search_fields = ('instrumento__tag', 'numero_certificado', 'responsavel', 'fornecedor')
    list_filter = ('resultado', 'data_calibracao', 'tem_selo_rbc', 'tipo_calibracao')
    autocomplete_fields = ['instrumento']
    filter_horizontal = ('padroes_utilizados',)


# --- NOVOS PAINEIS (SOLICITAÇÕES E OCORRÊNCIAS AVULSAS) ---

@admin.register(SolicitacaoInstrumento)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'solicitante', 'instrumento_alvo', 'status', 'data_solicitacao')
    list_filter = ('status', 'tipo')
    search_fields = ('solicitante__username', 'instrumento_alvo__tag')

@admin.register(Ocorrencia)
class OcorrenciaAdmin(admin.ModelAdmin):
    # Permite ver todas as ocorrências em uma lista única
    list_display = ('instrumento', 'tipo', 'data_ocorrencia', 'usuario_responsavel')
    list_filter = ('tipo', 'data_ocorrencia')
    search_fields = ('instrumento__tag',)

@admin.register(OrdemCalibracao)
class OrdemCalibracaoAdmin(admin.ModelAdmin):
    # Permite gerenciar envios e retornos de calibração
    list_display = ('instrumento', 'fornecedor', 'status', 'data_prevista')
    list_filter = ('status', 'tipo_local')
    search_fields = ('instrumento__tag', 'fornecedor')


# --- OUTROS CADASTROS (FORNECEDORES / COTACAO) ---

admin.site.register(Fornecedor)
admin.site.register(ProcessoCotacao)
admin.site.register(Orcamento)

# --- PROCEDIMENTOS E TREINAMENTOS ---

@admin.register(Procedimento)
class ProcedimentoAdmin(admin.ModelAdmin):
    def get_setor_nome(self, obj): return obj.setor.nome if obj.setor else "-"
    list_display = ('codigo', 'titulo', 'revisao_atual', 'get_setor_nome')
    search_fields = ('codigo', 'titulo')
    list_filter = ('setor',)

@admin.register(RegistroTreinamento)
class RegistroTreinamentoAdmin(admin.ModelAdmin):
    def procedimento_info(self, obj): return f"{obj.procedimento.codigo} (Rev. {obj.procedimento.revisao_atual})"
    def status_visual(self, obj): return format_html('<span style="color:green">VIGENTE</span>') if obj.status_treinamento == "VIGENTE" else format_html('<span style="color:red">PENDENTE</span>')
    list_display = ('colaborador', 'procedimento_info', 'revisao_treinada', 'status_visual')
    search_fields = ('colaborador__nome_completo', 'procedimento__codigo')
    list_filter = ('procedimento__codigo', 'revisao_treinada')
    autocomplete_fields = ['colaborador', 'procedimento']

@admin.register(PacoteTreinamento)
class PacoteTreinamentoAdmin(admin.ModelAdmin):
    filter_horizontal = ('procedimentos',)
    list_display = ('nome', 'count_docs')
    def count_docs(self, obj): return obj.procedimentos.count()