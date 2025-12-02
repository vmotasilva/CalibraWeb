from datetime import date

from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.utils.translation import gettext_lazy as _
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode

from .models import (
    AvaliacaoFornecedor, Ocorrencia, OcorrenciaInstrumento,
    CategoriaInstrumento, CentroCusto, Colaborador, DocumentoPessoal, FaixaMedicao, Ferias, Fornecedor,
    HierarquiaSetor, HistoricoCalibracao, Instrumento, Orcamento, OrdemCalibracao, PacoteTreinamento, Padrao,
    Procedimento, ProcessoCotacao, RegistroTreinamento, ResultadoFaixaCalibracao, Setor, SolicitacaoInstrumento, UnidadeMedida, Area, ProcedimentoRevisao
)


# --- Customização do AdminSite para Agrupamento ---
class CalibraAdminSite(admin.AdminSite):
    site_header = 'Calibra QMS - Administração'
    site_title = 'Calibra QMS Admin'
    index_title = 'Site administration'

    def get_app_list(self, request):
        # Agrupamento customizado
        app_dict = self._build_app_dict(request)
        # Ordem e títulos customizados
        ordering = [
            ('AUTH', _('Authentication and Authorization'), [
                'User', 'Group',
            ]),
            ('HR', _('HR'), [
                'Colaborador', 'Ferias', 'DocumentoPessoal', 'Ocorrencia', 'Vacation periods', 'Employee documents', 'Employee occurrences', 'Employees',
            ]),
            ('METROLOGY', _('Metrology'), [
                'Instrumento', 'FaixaMedicao', 'CategoriaInstrumento', 'Padrao', 'HistoricoCalibracao', 'OrdemCalibracao',
            ]),
            ('GED', _('Procedures & Training'), [
                'Procedimento', 'ProcedimentoRevisao', 'Area', 'RegistroTreinamento', 'PacoteTreinamento',
            ]),
            ('PERIODIC TASKS', _('Periodic Tasks'), [
                'Clocked', 'Crontabs', 'Intervals',
            ]),
            ('SUPPLY', _('Suppliers & Quotes'), [
                'Fornecedor', 'ProcessoCotacao', 'Orcamento',
            ]),
            ('REQUESTS', _('Requests'), [
                'SolicitacaoInstrumento',
            ]),
        ]
        custom_apps = []
        for code, title, models in ordering:
            app_models = []
            for model in models:
                for app in app_dict.values():
                    for m in app['models']:
                        if m['object_name'] == model or m['name'] == model:
                            app_models.append(m)
            if app_models:
                custom_apps.append({'name': title, 'app_label': code, 'models': app_models})
        # Adiciona apps não agrupados
        grouped = set(m['object_name'] for app in custom_apps for m in app['models'])
        for app in app_dict.values():
            extra_models = [m for m in app['models'] if m['object_name'] not in grouped]
            if extra_models:
                custom_apps.append({'name': app['name'], 'app_label': app['app_label'], 'models': extra_models})
        return custom_apps


# Substitui o site padrão
admin_site = CalibraAdminSite(name='calibra_admin')


# Formulário customizado para exibir permissões agrupadas
from django.contrib.auth.models import Permission
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm

class CustomUserChangeForm(DjangoUserChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dicionário para personalizar rótulos de modelos
        label_map = {
            'Faixamedicao': 'Faixa de Medição',
            'Categoria instrumento': 'Categoria do Instrumento',
            'Padrao': 'Padrão de Rastreabilidade',
            'Historico calibracao': 'Histórico de Calibração',
            'Ordem calibracao': 'Ordem de Calibração',
            'Instrumento': 'Instrumento',
            'Colaborador': 'Colaborador (RH)',
            'Ferias': 'Férias',
            'Documento pessoal': 'Documento Pessoal',
            'Ocorrencia': 'Ocorrência',
            'Procedimento': 'Procedimento',
            'Procedimentorevisao': 'Revisão de Procedimento',
            'Area': 'Área',
            'Registro treinamento': 'Registro de Treinamento',
            'Pacote treinamento': 'Pacote de Treinamento',
            'Fornecedor': 'Fornecedor',
            'Processo cotacao': 'Processo de Cotação',
            'Orcamento': 'Orçamento',
            'Solicitacao instrumento': 'Solicitação de Instrumento',
        }
        area_map = {
            'Faixamedicao': 'Metrologia',
            'Categoria instrumento': 'Metrologia',
            'Padrao': 'Metrologia',
            'Historico calibracao': 'Metrologia',
            'Ordem calibracao': 'Metrologia',
            'Instrumento': 'Metrologia',
            'Colaborador': 'RH',
            'Ferias': 'RH',
            'Documento pessoal': 'RH',
            'Ocorrencia': 'RH',
            'Procedimento': 'Procedimentos',
            'Procedimentorevisao': 'Procedimentos',
            'Area': 'Procedimentos',
            'Registro treinamento': 'Treinamentos',
            'Pacote treinamento': 'Treinamentos',
            'Fornecedor': 'Metrologia',
            'Processo cotacao': 'Metrologia',
            'Orcamento': 'Metrologia',
            'Solicitacao instrumento': 'Metrologia',
        }
        def custom_label(perm):
            ct = perm.content_type
            model_verbose = ct.model.replace('_', ' ').title()
            area = area_map.get(model_verbose, ct.app_label.title())
            model_label = label_map.get(model_verbose, model_verbose)
            return f"{area} | {model_label} | {perm.name.capitalize()}"
        self.fields['user_permissions'].label_from_instance = custom_label
        # Ordenar permissões pelo rótulo customizado
        perms = list(self.fields['user_permissions'].queryset)
        def sort_key(perm):
            ct = perm.content_type
            model_verbose = ct.model.replace('_', ' ').title()
            area = area_map.get(model_verbose, ct.app_label.title())
            model_label = label_map.get(model_verbose, model_verbose)
            return (area, model_label, perm.name)
        perms.sort(key=sort_key)
        self.fields['user_permissions'].queryset = Permission.objects.filter(pk__in=[p.pk for p in perms])

class CustomUserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informações pessoais', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissões', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'description': 'Defina o nível de acesso do usuário. Para acesso total, marque "Superuser". Para acesso restrito, selecione grupos e permissões específicas.'
        }),
        ('Datas importantes', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions')

admin_site.register(User, CustomUserAdmin)
admin_site.register(Group)


class CentroCustoInline(admin.TabularInline):
    model = CentroCusto
    extra = 1


class TreinamentoInline(admin.TabularInline):
    model = RegistroTreinamento
    extra = 0
    readonly_fields = ("status_visual",)
    fields = ("procedimento", "revisao_treinada", "data_treinamento", "status_visual")

    def status_visual(self, obj):
        return (
            format_html('<span style="color:green">VIGENTE</span>')
            if obj.status_treinamento == "VIGENTE"
            else format_html('<span style="color:red">PENDENTE</span>')
        )


class FeriasInline(admin.TabularInline):
    model = Ferias
    extra = 1


class DocumentoPessoalInline(admin.TabularInline):
    model = DocumentoPessoal
    extra = 1


# --- INLINES ESPECÍFICOS DE OCORRÊNCIAS ---


# Inline para Ocorrências de RH (Colaborador)
class OcorrenciaRHInline(admin.TabularInline):
    model = Ocorrencia
    extra = 0
    # Ajuste os campos conforme o que existe no seu model Ocorrencia de RH.
    # Se tiver dúvida, verifique seu models.py. Assumindo campos comuns:
    # fields = ('data_ocorrencia', 'motivo', 'descricao') # Exemplo


# Inline para Ocorrências de Metrologia (Instrumento)
class OcorrenciaInstrumentoInline(admin.TabularInline):
    model = OcorrenciaInstrumento
    extra = 0
    fields = ("tipo", "data_ocorrencia", "usuario_responsavel", "descricao")
    readonly_fields = ("data_ocorrencia",)


class CalibracaoInline(admin.TabularInline):
    model = OrdemCalibracao
    extra = 0
    fields = (
        "fornecedor",
        "tipo_local",
        "status",
        "data_prevista",
        "data_envio",
        "data_retorno",
    )


class FaixaMedicaoInline(admin.TabularInline):
    model = FaixaMedicao
    extra = 1


# --- FILTROS PERSONALIZADOS ---


class SetorPorGrupoFilter(admin.SimpleListFilter):
    title = "Setor (Dinâmico)"
    parameter_name = "setor_id"

    def lookups(self, request, model_admin):
        g = request.GET.get("grupo")
        qs = (
            Setor.objects.filter(colaborador__grupo=g).distinct()
            if g
            else Setor.objects.filter(colaborador__isnull=False).distinct()
        )
        return [(s.id, s.nome) for s in qs]

    def queryset(self, request, queryset):
        return queryset.filter(setor__id=self.value()) if self.value() else queryset


# --- CADASTROS PRINCIPAIS (RH / ESTRUTURA) ---


@admin.register(Setor, site=admin_site)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "listar_ccs", "responsavel")
    search_fields = ("nome",)
    inlines = [CentroCustoInline]

    def listar_ccs(self, obj):
        return ", ".join([c.codigo for c in obj.centros_custo.all()])


@admin.register(CentroCusto, site=admin_site)
class CentroCustoAdmin(admin.ModelAdmin):
    search_fields = ("codigo", "descricao", "setor__nome")
    list_display = ("codigo", "descricao", "setor")


@admin.register(Colaborador, site=admin_site)
class ColaboradorAdmin(admin.ModelAdmin):
    def get_setor_nome(self, obj):
        return obj.setor.nome if obj.setor else "-"

    def get_cc_code(self, obj):
        return obj.centro_custo.codigo if obj.centro_custo else "-"

    list_display = (
        "matricula",
        "cpf",
        "nome_completo",
        "cargo",
        "lider",
        "supervisor",
        "gerente",
        "grupo",
        "get_setor_nome",
        "salario",
        "em_ferias",
        "is_active",
    )
    search_fields = ("matricula", "cpf", "nome_completo", "cargo")
    list_filter = ("is_active", "em_ferias", "grupo", SetorPorGrupoFilter, "turno")
    autocomplete_fields = ["setor", "centro_custo", "lider", "supervisor", "gerente"]
    filter_horizontal = ("pacotes_treinamento",)

    # CORREÇÃO: Usando o Inline correto para RH
    inlines = [
        FeriasInline,
        DocumentoPessoalInline,
        TreinamentoInline,
        OcorrenciaRHInline,
    ]

    fieldsets = (
        ("Identificação", {"fields": (("matricula", "cpf"), "nome_completo")}),
        (
            "Lotação e Cargo",
            {
                "fields": (
                    ("cargo", "salario"),
                    ("lider", "supervisor", "gerente"),
                    ("grupo", "turno"),
                    ("setor", "centro_custo"),
                )
            },
        ),
        ("Treinamentos", {"fields": ("pacotes_treinamento",)}),
        ("Controle", {"fields": ("is_active", "em_ferias")}),
    )


@admin.register(HierarquiaSetor, site=admin_site)
class HierarquiaSetorAdmin(admin.ModelAdmin):
    list_display = ("setor", "turno", "lider", "supervisor", "gerente")
    list_filter = ("setor", "turno")
    autocomplete_fields = ["lider", "supervisor", "gerente", "diretor", "setor"]
    actions = ["duplicar_hierarquia"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for c in ["lider", "supervisor", "gerente", "diretor", "setor"]:
            if c in form.base_fields:
                w = form.base_fields[c].widget
                w.can_add_related = False
                w.can_change_related = False
                w.can_delete_related = False
        return form

    @admin.action(description="Duplicar")
    def duplicar_hierarquia(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Selecione UMA", level="warning")
            return
        o = queryset.first()
        base = reverse("admin:qms_hierarquiasetor_add")
        qs = urlencode(
            {
                "setor": o.setor.id,
                "lider": o.lider.id if o.lider else "",
                "supervisor": o.supervisor.id if o.supervisor else "",
                "gerente": o.gerente.id if o.gerente else "",
                "diretor": o.diretor.id if o.diretor else "",
            }
        )
        return redirect(f"{base}?{qs}")


# --- CONFIGURAÇÕES DE METROLOGIA (INSTRUMENTOS) ---


@admin.register(UnidadeMedida, site=admin_site)
class UnidadeMedidaAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla")
    search_fields = ("nome", "sigla")


@admin.register(CategoriaInstrumento, site=admin_site)
class CategoriaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao", "unidade_padrao")
    search_fields = ("nome", "descricao", "unidade_padrao__sigla")
    autocomplete_fields = ["unidade_padrao"]


@admin.register(Padrao, site=admin_site)
class PadraoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descricao", "data_validade", "status_validade", "ativo")
    search_fields = ("codigo", "descricao", "numero_certificado")
    list_filter = ("ativo",)

    def status_validade(self, obj):
        if obj.esta_vencido:
            return format_html(
                '<span style="color:red; font-weight:bold;">VENCIDO</span>'
            )
        return format_html('<span style="color:green;">VIGENTE</span>')

    status_validade.short_description = "Validade"


@admin.register(Instrumento, site=admin_site)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = (
        "tag",
        "descricao",
        "categoria",
        "responsavel",
        "data_proxima_calibracao",
        "ativo",
    )
    search_fields = ("tag", "codigo", "descricao", "modelo", "serie")
    list_filter = ("categoria", "ativo", "setor")
    autocomplete_fields = ["responsavel", "setor", "categoria"]

    # CORREÇÃO: Usando o Inline correto para Instrumentos
    inlines = [FaixaMedicaoInline, OcorrenciaInstrumentoInline, CalibracaoInline]

    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "tag",
                    "codigo",
                    "descricao",
                    "fabricante",
                    "modelo",
                    "serie",
                    "categoria",
                )
            },
        ),
        (
            "Localização e Responsável",
            {"fields": ("setor", "responsavel", "localizacao")},
        ),
        (
            "Calibração",
            {
                "fields": (
                    "frequencia_meses",
                    "data_ultima_calibracao",
                    "data_proxima_calibracao",
                    "ativo",
                )
            },
        ),
    )


@admin.register(HistoricoCalibracao, site=admin_site)
class HistoricoCalibracaoAdmin(admin.ModelAdmin):
    list_display = (
        "instrumento",
        "certificado",
        "data_calibracao",
        "resultado",
        "fornecedor",
        "tem_selo_rbc",
    )
    search_fields = (
        "instrumento__tag",
        "numero_certificado",
        "responsavel",
        "fornecedor",
    )
    list_filter = ("resultado", "data_calibracao", "tem_selo_rbc", "tipo_calibracao")
    autocomplete_fields = ["instrumento"]
    filter_horizontal = ("padroes_utilizados",)


@admin.register(ResultadoFaixaCalibracao, site=admin_site)
class ResultadoFaixaCalibracaoAdmin(admin.ModelAdmin):
    list_display = (
        "historico",
        "faixa_medicao",
        "erro_encontrado",
        "incerteza",
        "tolerancia_usada",
        "resultado",
        "desconsiderada",
    )
    search_fields = (
        "historico__numero_certificado",
        "historico__instrumento__tag",
        "faixa_medicao__valor_minimo",
        "faixa_medicao__valor_maximo",
    )
    list_filter = ("resultado", "desconsiderada")
    autocomplete_fields = ["historico", "faixa_medicao"]
    readonly_fields = ("resultado",)


# --- NOVOS PAINEIS (SOLICITAÇÕES E OCORRÊNCIAS AVULSAS) ---


@admin.register(SolicitacaoInstrumento, site=admin_site)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo",
        "solicitante",
        "instrumento_alvo",
        "status",
        "data_solicitacao",
    )
    list_filter = ("status", "tipo")
    search_fields = ("solicitante__username", "instrumento_alvo__tag")


# CORREÇÃO: OcorrenciaAdmin separado para RH
@admin.register(Ocorrencia, site=admin_site)
class OcorrenciaAdmin(admin.ModelAdmin):
    # Ajuste os campos conforme seu model de RH
    list_display = ("colaborador", "data_ocorrencia")
    search_fields = ("colaborador__nome_completo",)


# CORREÇÃO: OcorrenciaInstrumentoAdmin separado para Metrologia
@admin.register(OcorrenciaInstrumento, site=admin_site)
class OcorrenciaInstrumentoAdmin(admin.ModelAdmin):
    list_display = ("instrumento", "tipo", "data_ocorrencia", "usuario_responsavel")
    list_filter = ("tipo", "data_ocorrencia")
    search_fields = ("instrumento__tag",)


@admin.register(OrdemCalibracao, site=admin_site)
class OrdemCalibracaoAdmin(admin.ModelAdmin):
    list_display = ("instrumento", "fornecedor", "status", "data_prevista")
    list_filter = ("status", "tipo_local")
    search_fields = ("instrumento__tag", "fornecedor")


# --- OUTROS CADASTROS (FORNECEDORES / COTACAO) ---

admin.site.register(Fornecedor)
admin.site.register(ProcessoCotacao)
admin.site.register(Orcamento)

# --- PROCEDIMENTOS E TREINAMENTOS ---


@admin.register(Procedimento, site=admin_site)
class ProcedimentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "numero_revisao", "classificacao", "autor")
    search_fields = ("codigo", "nome", "autor", "classificacao")
    list_filter = ("classificacao",)


@admin.register(RegistroTreinamento, site=admin_site)
class RegistroTreinamentoAdmin(admin.ModelAdmin):
    def procedimento_info(self, obj):
        return f"{obj.procedimento.codigo} (Rev. {obj.procedimento.revisao_atual})"

    def status_visual(self, obj):
        return (
            format_html('<span style="color:green">VIGENTE</span>')
            if obj.status_treinamento == "VIGENTE"
            else format_html('<span style="color:red">PENDENTE</span>')
        )

    list_display = (
        "colaborador",
        "procedimento_info",
        "revisao_treinada",
        "status_visual",
    )
    search_fields = ("colaborador__nome_completo", "procedimento__codigo")
    list_filter = ("procedimento__codigo", "revisao_treinada")
    autocomplete_fields = ["colaborador", "procedimento"]


@admin.register(PacoteTreinamento, site=admin_site)
class PacoteTreinamentoAdmin(admin.ModelAdmin):
    @admin.register(Area, site=admin_site)
    class AreaAdmin(admin.ModelAdmin):
        list_display = ("nome", "descricao")
        search_fields = ("nome", "descricao")

    @admin.register(ProcedimentoRevisao, site=admin_site)
    class ProcedimentoRevisaoAdmin(admin.ModelAdmin):
        list_display = ("procedimento", "revisao", "data_revisao", "data_aprovacao", "elaborador", "revisor", "aprovador", "criado_em")
        search_fields = ("procedimento__codigo", "revisao")

    # Registros simples
    admin_site.register(Fornecedor)
    admin_site.register(ProcessoCotacao)
    admin_site.register(Orcamento)
    filter_horizontal = ("procedimentos",)
    list_display = ("nome", "count_docs")

    def count_docs(self, obj):
        return obj.procedimentos.count()
