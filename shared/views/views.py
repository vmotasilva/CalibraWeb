# -*- coding: utf-8 -*-
"""
Views compartilhadas - Dashboard, Health Check, Templates e Admin
"""

import io
import json
import os
import tempfile
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
import logging
from django.conf import settings
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Imports dos models
from metrologia.models import Instrumento
from procedures.models import ProcessoCotacao, RegistroTreinamento
from rh.models import Colaborador
from organization.models import CentroCusto
from qms.models import SolicitacaoInstrumento, ImportJob

try:
    _otp_installed = any(
        (app == 'django_otp' or app.startswith('django_otp.') or app.startswith('otp_'))
        for app in getattr(settings, 'INSTALLED_APPS', [])
    )
    if _otp_installed:
        from django_otp.plugins.otp_totp.models import TOTPDevice  # type: ignore
    else:
        TOTPDevice = None
except Exception:
    TOTPDevice = None

# Imports dos helpers
from qms.views_helpers import dl_df, dl_generic, parse_date
from shared.notifications import get_user_cobrancas_counts, get_user_cobrancas_items
from shared.permissions import has_module_access, has_view_access


# ==============================================================================
# DASHBOARD E HEALTH CHECK
# ==============================================================================

@login_required
def home_view(request):
    """Página inicial unificada: Calibra HUB de Módulos."""
    return hub_view(request)


def _hub_safe_reverse(view_name, *args, **kwargs):
    try:
        return reverse(view_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def _hub_can_access(user, module_key, view_name=None):
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    if not has_module_access(user, module_key):
        return False

    if view_name and not has_view_access(user, view_name):
        return False

    return True


MODULE_HUBS_CONFIG = {
    "auditoria": {
        "id": "auditoria",
        "title": "Auditoria",
        "module_key": "auditoria",
        "badge": "Qualidade & Conformidade",
        "description": "Central de gestão de auditorias internas, modelos de questionários, avaliações de conformidade e rotinas programadas.",
        "icon": "bi-clipboard-data",
        "color": "#7c3aed",
        "color_light": "#f5f3ff",
        "color_border": "rgba(124, 58, 237, 0.4)",
        "gradient": "linear-gradient(135deg, #1e1035 0%, #3b1366 50%, #6d28d9 100%)",
        "icon_bg": "#6d28d9",
        "activities": [
            {
                "title": "Dashboard de Auditoria",
                "description": "Acompanhe o calendário mensal, auditorias agendadas e os indicadores consolidados de conformidade.",
                "icon": "bi-bar-chart-line",
                "view_name": "auditoria:dashboard",
                "badge": "Indicadores",
            },
            {
                "title": "Preencher Auditoria",
                "description": "Inicie a execução e preenchimento de uma nova auditoria a partir de um questionário ativo.",
                "icon": "bi-journal-plus",
                "view_name": "auditoria:selecionar_modelo_preenchimento",
                "badge": "Operacional",
            },
            {
                "title": "Modelos de Questionários",
                "description": "Crie, edite e estruture questionários, tópicos e critérios de avaliação de auditoria.",
                "icon": "bi-folder2-open",
                "view_name": "auditoria:modelos_list",
                "badge": "Configuração",
            },
            {
                "title": "Registros de Auditoria",
                "description": "Consulte o histórico de auditorias concluídas, relatórios emitidos e gere exportações em PDF.",
                "icon": "bi-file-earmark-check",
                "view_name": "auditoria:registros_list",
                "badge": "Histórico",
            },
            {
                "title": "Banco de Perguntas",
                "description": "Gerencie a biblioteca central de perguntas, requisitos e normas de auditoria.",
                "icon": "bi-question-diamond",
                "view_name": "auditoria:perguntas_list",
                "badge": "Biblioteca",
            },
            {
                "title": "Auditorias ISO 13485",
                "description": "Rotinas específicas de entrevistas e checagem de conformidade com a norma ISO 13485.",
                "icon": "bi-patch-check",
                "view_name": "auditoria:iso_auditoria_list",
                "badge": "Normas",
            },
        ],
    },
    "metrologia": {
        "id": "metrologia",
        "title": "Metrologia",
        "module_key": "metrologia",
        "badge": "Instrumentos & Calibração",
        "description": "Gestão completa do parque de instrumentos de medição, histórico de calibrações, certificados e cotações externas.",
        "icon": "bi-rulers",
        "color": "#0284c7",
        "color_light": "#f0f9ff",
        "color_border": "rgba(2, 132, 199, 0.4)",
        "gradient": "linear-gradient(135deg, #082138 0%, #0c3b64 50%, #0284c7 100%)",
        "icon_bg": "#0369a1",
        "activities": [
            {
                "title": "Lista de Instrumentos",
                "description": "Consulte todos os instrumentos ativos, vencimentos de calibração, responsáveis e certificados.",
                "icon": "bi-list-check",
                "view_name": "modulo_metrologia",
                "badge": "Acervo",
            },
            {
                "title": "Novo Instrumento",
                "description": "Cadastre um novo instrumento de medição, definindo faixas, fabricante, modelo e tolerâncias.",
                "icon": "bi-plus-circle",
                "view_name": "novo_instrumento",
                "badge": "Cadastro",
            },
            {
                "title": "Cotações de Calibração",
                "description": "Gerencie solicitações de cotação com laboratórios parceiros, propostas comerciais e aprovações.",
                "icon": "bi-cash-stack",
                "view_name": "metrologia:solicitacao_list",
                "badge": "Orçamentos",
            },
            {
                "title": "Categorias de Instrumentos",
                "description": "Organize grupos de instrumentos, critérios de periodicidade e faixas de calibração padrão.",
                "icon": "bi-tags",
                "view_name": "metrologia:categorias_list",
                "badge": "Classificação",
            },
            {
                "title": "Unidades de Medida",
                "description": "Cadastre e configure unidades físicas de medição utilizadas nos certificados e tolerâncias.",
                "icon": "bi-rulers",
                "view_name": "metrologia:unidades_list",
                "badge": "Parâmetros",
            },
            {
                "title": "Etiquetas e Exportação",
                "description": "Gere etiquetas com QR code para identificação nos equipamentos e exporte dados para Excel.",
                "icon": "bi-upc-scan",
                "view_name": "export_etiquetas",
                "badge": "Impressão",
            },
            {
                "title": "Histórico de Substituições",
                "description": "Rastreie trocas de instrumentos equivalentes e histórico de referências substituídas.",
                "icon": "bi-arrow-left-right",
                "view_name": "listar_substitucoes",
                "badge": "Rastreabilidade",
            },
        ],
    },
    "treinamentos": {
        "id": "treinamentos",
        "title": "Treinamentos",
        "module_key": "procedures",
        "badge": "Capacitação & Procedimentos",
        "description": "Matriz de competências, procedimentos operacionais (POP/IT), cronograma de treinamentos e avaliações de eficácia.",
        "icon": "bi-mortarboard",
        "color": "#2563eb",
        "color_light": "#eff6ff",
        "color_border": "rgba(37, 99, 235, 0.4)",
        "gradient": "linear-gradient(135deg, #0b1938 0%, #1e3a8a 50%, #2563eb 100%)",
        "icon_bg": "#1d4ed8",
        "activities": [
            {
                "title": "Dashboard de Treinamentos",
                "description": "Visão geral de conformidade, indicadores de qualificação por equipe, demandas e pendências.",
                "icon": "bi-speedometer2",
                "view_name": "procedures:dashboard_treinamentos",
                "badge": "Visão Geral",
            },
            {
                "title": "Matriz de Habilidades Geral",
                "description": "Acompanhe a matriz consolidada de colaboradores, cargos, setores e procedimentos obrigatórios.",
                "icon": "bi-award",
                "view_name": "procedures:matrizes_list",
                "badge": "Competências",
            },
            {
                "title": "Avaliações de Habilidade",
                "description": "Matriz completa de avaliações, notas e proficiência por colaborador e disciplina.",
                "icon": "bi-check2-square",
                "view_name": "procedures:matriz_avaliacoes",
                "badge": "Avaliações",
            },
            {
                "title": "Procedimentos e Instruções",
                "description": "Acesse, cadastre e revise procedimentos operacionais padrão (POP), instruções e formulários.",
                "icon": "bi-journal-text",
                "view_name": "procedures:procedimentos_list",
                "badge": "Normativos",
            },
            {
                "title": "Planejamento de Treinamentos",
                "description": "Agende novos treinamentos, defina datas, instrutores, colaboradores convocados e acompanhe status.",
                "icon": "bi-calendar-event",
                "view_name": "procedures:planejamentos_list",
                "badge": "Planejamento",
            },
            {
                "title": "Validações Pendentes",
                "description": "Avalie e homologue pendências na matriz de habilidades de colaboradores recém-treinados.",
                "icon": "bi-patch-check",
                "view_name": "procedures:validacoes_pendentes",
                "badge": "Homologação",
            },
            {
                "title": "Histórico de Treinamentos",
                "description": "Consulte o acervo de treinamentos concluídos, listas de presença digitalizadas e registros históricos.",
                "icon": "bi-clock-history",
                "view_name": "procedures:treinamentos_list",
                "badge": "Histórico",
            },
            {
                "title": "Calendário de Treinamentos",
                "description": "Visualização mensal em formato de grade com as sessões programadas e suas respectivas salas/áreas.",
                "icon": "bi-calendar3",
                "view_name": "procedures:treinamentos_calendario",
                "badge": "Agenda",
            },
            {
                "title": "Avaliação de Eficácia",
                "description": "Acompanhe e registre a avaliação pós-treinamento realizada pelos gestores e líderes de setor.",
                "icon": "bi-check2-circle",
                "view_name": "procedures:avaliacao_eficacia_list",
                "badge": "Eficácia",
            },
            {
                "title": "Perguntas de Auto-Avaliação",
                "description": "Banco de perguntas do formulário FOR.141 para avaliação de eficácia de procedimentos.",
                "icon": "bi-question-circle",
                "view_name": "procedures:perguntas_avaliacao_list",
                "badge": "FOR.141",
            },
        ],
    },
    "boards": {
        "id": "boards",
        "title": "Quadros",
        "module_key": "boards",
        "badge": "Gestão Visual & Kanban",
        "description": "Gestão ágil de fluxos de trabalho, cartões com prazos e checklists, acompanhamento de projetos e comunicação da equipe.",
        "icon": "bi-kanban",
        "color": "#0891b2",
        "color_light": "#ecfeff",
        "color_border": "rgba(8, 145, 178, 0.4)",
        "gradient": "linear-gradient(135deg, #062a33 0%, #0e5b6b 50%, #0891b2 100%)",
        "icon_bg": "#0e7490",
        "activities": [
            {
                "title": "Painel de Quadros",
                "description": "Acesse e gerencie todos os fluxos de trabalho kanban, quadros departamentais e projetos ativos.",
                "icon": "bi-kanban",
                "view_name": "boards:dashboard",
                "badge": "Principal",
            },
            {
                "title": "Fluxos e Demandas",
                "description": "Mova cartões, defina prioridades, prazos limites e organize colunas operacionais da equipe.",
                "icon": "bi-card-checklist",
                "view_name": "boards:dashboard",
                "badge": "Operações",
            },
        ],
    },
    "laboratorio": {
        "id": "laboratorio",
        "title": "Laboratório",
        "module_key": "laboratorio",
        "badge": "Operações Técnicas",
        "description": "Registro de ocorrências técnicas, manutenção preventiva e corretiva de máquinas, tratamentos e indicadores analíticos.",
        "icon": "bi-flask",
        "color": "#059669",
        "color_light": "#ecfdf5",
        "color_border": "rgba(5, 150, 105, 0.4)",
        "gradient": "linear-gradient(135deg, #05261d 0%, #064e3b 50%, #059669 100%)",
        "icon_bg": "#047857",
        "activities": [
            {
                "title": "Painel de Ocorrências",
                "description": "Consulte e acompanhe todas as ocorrências abertas, em andamento e histórico de encerramentos.",
                "icon": "bi-card-list",
                "view_name": "laboratorio:modulo",
                "badge": "Ocorrências",
            },
            {
                "title": "Dashboard do Laboratório",
                "description": "Métricas de tempo de resposta, volume de não conformidades, gráficos por máquina e relatórios.",
                "icon": "bi-speedometer2",
                "view_name": "laboratorio:dashboard",
                "badge": "Indicadores",
            },
            {
                "title": "Registrar Nova Ocorrência",
                "description": "Abra um novo chamado técnico ou aponte anomalias operacionais no ambiente laboratorial.",
                "icon": "bi-plus-square",
                "view_name": "laboratorio:ocorrencia_create",
                "badge": "Novo Registro",
            },
            {
                "title": "Parque de Máquinas",
                "description": "Consulte equipamentos do laboratório, especificações técnicas e histórico de intervenções.",
                "icon": "bi-gear-wide-connected",
                "view_name": "maquinas:maquinas_list",
                "badge": "Equipamentos",
            },
            {
                "title": "Tratamento Antirreflexo",
                "description": "Controle de lotes, inspeções visuais e acompanhamento de tratamentos ópticos especiais.",
                "icon": "bi-infinity",
                "view_name": "laboratorio:tratamento_list",
                "badge": "Processos",
            },
            {
                "title": "Categorias de Ocorrência",
                "description": "Classificações, motivos de paradas e tipos de defeitos para padronização de registros.",
                "icon": "bi-tags",
                "view_name": "laboratorio:categorias_list",
                "badge": "Parâmetros",
            },
        ],
    },
    "pessoas": {
        "id": "pessoas",
        "title": "Pessoas",
        "module_key": "rh",
        "badge": "Recursos Humanos & Equipe",
        "description": "Quadro de colaboradores, estrutura de liderança, escalas de férias, horas extras convocadas e controle de acessos.",
        "icon": "bi-people",
        "color": "#ea580c",
        "color_light": "#fff7ed",
        "color_border": "rgba(234, 88, 12, 0.4)",
        "gradient": "linear-gradient(135deg, #2e1205 0%, #7c2d12 50%, #ea580c 100%)",
        "icon_bg": "#c2410c",
        "activities": [
            {
                "title": "Quadro de Colaboradores",
                "description": "Visão centralizada de colaboradores ativos, cargos, setores, lideranças e centros de custo.",
                "icon": "bi-people-fill",
                "view_name": "modulo_rh",
                "badge": "Equipe",
            },
            {
                "title": "Novo Colaborador",
                "description": "Cadastre um novo colaborador na organização preenchendo matrícula, cargo, setor e centro de custo.",
                "icon": "bi-person-plus",
                "view_name": "rh:criar_colaborador",
                "badge": "Cadastro",
            },
            {
                "title": "Gestão e Escala de Férias",
                "description": "Programação de descanso anual, controle de períodos aquisitivos e calendário de férias da equipe.",
                "icon": "bi-calendar-check",
                "view_name": "rh:gestao_ferias",
                "badge": "Férias",
            },
            {
                "title": "Planejamento de Horas Extras",
                "description": "Convocação, aprovação e monitoramento das horas extras programadas pelos líderes de setor.",
                "icon": "bi-clock-history",
                "view_name": "rh:planejamento_hora_extra_list",
                "badge": "Jornada",
            },
            {
                "title": "Usuários e Acessos",
                "description": "Administre contas de login no sistema, permissões de acesso aos módulos e autenticação em 2 etapas.",
                "icon": "bi-person-gear",
                "view_name": "rh:listar_usuarios",
                "badge": "Segurança",
            },
            {
                "title": "Demandas e Falhas de Ponto",
                "description": "Gerenciamento de justificativas, inconsistências de batidas de ponto e regularizações.",
                "icon": "bi-fingerprint",
                "view_name": "rh:demandas_falhas_ponto",
                "badge": "Ponto",
            },
        ],
    },
    "fornecedores": {
        "id": "fornecedores",
        "title": "Fornecedores",
        "module_key": "fornecedores",
        "badge": "Qualificação & Suprimentos",
        "description": "Base de fornecedores homologados, monitoramento de desempenho, matriz de qualificação e documentação obrigatória.",
        "icon": "bi-truck",
        "color": "#c026d3",
        "color_light": "#fdf4ff",
        "color_border": "rgba(192, 38, 211, 0.4)",
        "gradient": "linear-gradient(135deg, #2e083a 0%, #701a75 50%, #c026d3 100%)",
        "icon_bg": "#a21caf",
        "activities": [
            {
                "title": "Base de Fornecedores",
                "description": "Consulte a lista completa de fornecedores ativos, contatos comerciais e categorias fornecidas.",
                "icon": "bi-building",
                "view_name": "fornecedores:fornecedor_list",
                "badge": "Cadastro",
            },
            {
                "title": "Novo Fornecedor",
                "description": "Cadastre um novo fornecedor para processo de homologação, cotação e avaliação da qualidade.",
                "icon": "bi-building-add",
                "view_name": "fornecedores:fornecedor_create",
                "badge": "Novo",
            },
            {
                "title": "Painel & Avaliações",
                "description": "Acesse a matriz de fornecedores, histórico de avaliações periódicas e critérios de seleção.",
                "icon": "bi-stars",
                "view_name": "fornecedores:modulo",
                "badge": "Desempenho",
            },
        ],
    },
}


@login_required
def module_hub_view(request, module_slug):
    """HUB dedicado de um módulo específico, listando todas as suas atividades."""
    slug = module_slug.lower().strip()
    config = MODULE_HUBS_CONFIG.get(slug)
    if not config:
        # Tentar mapear aliases comuns
        alias_map = {
            "procedimentos": "treinamentos",
            "training": "treinamentos",
            "rh": "pessoas",
            "quadros": "boards",
        }
        target_slug = alias_map.get(slug)
        config = MODULE_HUBS_CONFIG.get(target_slug) if target_slug else None

    if not config:
        messages.error(request, "Módulo não encontrado.")
        return redirect("hub")

    # Verificar se o usuário tem permissão para o módulo
    if not _hub_can_access(request.user, config["module_key"]):
        messages.error(request, f"Você não possui permissão para acessar o módulo {config['title']}.")
        return redirect("hub")

    # Filtrar atividades liberadas para o usuário
    activities = []
    for act in config.get("activities", []):
        url = _hub_safe_reverse(act["view_name"])
        if not url:
            continue
        if not _hub_can_access(request.user, config["module_key"], act["view_name"]):
            continue
        activities.append({
            "title": act["title"],
            "description": act["description"],
            "icon": act["icon"],
            "badge": act.get("badge", ""),
            "url": url,
        })

    return render(
        request,
        "shared/module_hub.html",
        {
            "module": config,
            "activities": activities,
        },
    )


def auditoria_hub_view(request):
    return module_hub_view(request, "auditoria")


def metrologia_hub_view(request):
    return module_hub_view(request, "metrologia")


def procedures_hub_view(request):
    return module_hub_view(request, "treinamentos")


def boards_hub_view(request):
    return module_hub_view(request, "boards")


def laboratorio_hub_view(request):
    return module_hub_view(request, "laboratorio")


def rh_hub_view(request):
    return module_hub_view(request, "pessoas")


def fornecedores_hub_view(request):
    return module_hub_view(request, "fornecedores")


@login_required
def hub_view(request):
    """Página inicial do Calibra HUB: direcionamento aos HUBS dedicados dos módulos."""
    modules = []
    for cfg in MODULE_HUBS_CONFIG.values():
        if not _hub_can_access(request.user, cfg["module_key"]):
            continue

        url = _hub_safe_reverse("module_hub", module_slug=cfg["id"])
        if not url:
            continue

        modules.append(
            {
                "id": cfg["id"],
                "title": cfg["title"],
                "description": cfg["description"],
                "icon": cfg["icon"],
                "color": cfg["color"],
                "url": url,
            }
        )

    hub_stats = [
        {
            "label": "Módulos liberados",
            "value": len(modules),
            "detail": "áreas disponíveis no sistema",
        },
        {
            "label": "Favoritos",
            "value": 0,
            "detail": "módulos fixados no topo",
            "dynamic_id": "hub-favorites-count",
        },
    ]

    return render(
        request,
        "shared/hub.html",
        {
            "hub_stats": hub_stats,
            "modules": modules,
            "quick_actions": [],
            "pending_items": [],
        },
    )

@login_required
def inbox_view(request):
    """View dedicada à Caixa de Entrada de tarefas pendentes individuais, organizada em abas por módulo."""
    from shared.inbox import get_user_inbox_items
    from collections import OrderedDict
    from django.utils.text import slugify

    can_toggle_global = request.user.is_superuser or request.user.is_staff

    if can_toggle_global and 'global' in request.GET:
        if request.GET.get('global') == '1':
            request.session['inbox_global'] = True
        else:
            request.session['inbox_global'] = False

    inbox_is_global = request.session.get('inbox_global', False)

    inbox_items = get_user_inbox_items(request.user, is_global=inbox_is_global)

    active_tab = (request.GET.get('tab') or 'todas').strip().lower()
    active_sub = (request.GET.get('sub') or 'todas').strip().lower()

    module_icons = {
        "auditoria": "bi-clipboard-check",
        "quadros": "bi-kanban",
        "metrologia": "bi-tools",
        "treinamentos": "bi-mortarboard",
        "fornecedores": "bi-truck",
        "laboratorio": "bi-droplet-half",
        "pessoas": "bi-people",
    }

    # Agrupar por módulo e por sub-origem/sub-aba
    grouped_items: dict[str, dict[str, Any]] = OrderedDict()
    for item in inbox_items:
        mod_name = (item.module or "Outros").strip().capitalize()
        mod_key = mod_name.lower()
        if mod_key not in grouped_items:
            icon = module_icons.get(mod_key, item.icon or "bi-bell")
            grouped_items[mod_key] = {
                "name": mod_name,
                "slug": slugify(mod_name),
                "icon": icon,
                "items": [],
                "sub_groups": OrderedDict(),
            }
        grouped_items[mod_key]["items"].append(item)

        sub_name = (item.sub_type or "Geral").strip()
        sub_slug = slugify(sub_name)
        if sub_slug not in grouped_items[mod_key]["sub_groups"]:
            grouped_items[mod_key]["sub_groups"][sub_slug] = {
                "name": sub_name,
                "slug": sub_slug,
                "count": 0,
                "items": [],
            }
        grouped_items[mod_key]["sub_groups"][sub_slug]["count"] += 1
        grouped_items[mod_key]["sub_groups"][sub_slug]["items"].append(item)

    return render(
        request,
        "shared/inbox_page.html",
        {
            "inbox_items": inbox_items,
            "grouped_items": grouped_items,
            "active_tab": active_tab,
            "active_sub": active_sub,
            "can_toggle_global": can_toggle_global,
            "inbox_is_global": inbox_is_global,
        },
    )

@login_required
def changelog_view(request):
    """View para exibir a página inteira de histórico de alterações."""
    return render(request, "shared/changelog_page.html")


def dashboard_view(request):
    """Dashboard principal de metrologia agregando dados otimizados."""
    try:
        from metrologia.views.views import get_metrologia_dashboard_data
        data = get_metrologia_dashboard_data()
        ctx = {
            "nome_display": request.user.username if request.user.is_authenticated else "Visitante",
            "data": data,
            "kpis": data["kpis"],
            "instrumentos": data["instrumentos"],
            "solicitacoes_cotacao": data["solicitacoes_cotacao"],
            "qtd_pendentes": data["qtd_solicitacoes_qms"],
            "today": data["hoje"],
            "hoje_display": data["hoje_display"],
            "categorias": data.get("categorias", []),
            "setores": data.get("setores", []),
            "categorias_filtro": data.get("categorias_filtro", []),
            "setores_filtro": data.get("setores_filtro", []),
            "periodos_filtro": data.get("periodos_filtro", []),
            "fornecedores": data.get("fornecedores", []),
        }
    except Exception as e:
        from datetime import date
        ctx = {
            "nome_display": request.user.username if request.user.is_authenticated else "Visitante",
            "data": {"kpis": {"todos": {}, "externo": {}, "interno": {}}, "instrumentos": []},
            "kpis": {"todos": {}, "externo": {}, "interno": {}},
            "instrumentos": [],
            "solicitacoes_cotacao": [],
            "qtd_pendentes": 0,
            "today": date.today().strftime('%Y-%m-%d'),
            "hoje_display": date.today().strftime('%d/%m/%Y'),
            "categorias": [],
            "setores": [],
            "categorias_filtro": [],
            "setores_filtro": [],
            "periodos_filtro": [],
            "fornecedores": [],
            "error": str(e),
        }
    return render(request, "shared/dashboard.html", ctx)


def health_check(request):
    """Lightweight health check endpoint for monitoring."""
    return HttpResponse("OK", content_type="text/plain")


# ==============================================================================
# ACCOUNT / PASSWORD APIs
# ==============================================================================


@login_required
@require_POST
def api_change_password(request):
    """Troca a senha do usuário logado.

    Espera JSON:
    - current_password
    - new_password
    - confirm_password
    """
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    current_password = (data.get('current_password') or '').strip()
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not current_password or not new_password or not confirm_password:
        return JsonResponse({'success': False, 'error': 'Preencha todos os campos.'}, status=400)

    if new_password != confirm_password:
        return JsonResponse({'success': False, 'error': 'As senhas novas não conferem.'}, status=400)

    user = request.user
    if not user.check_password(current_password):
        return JsonResponse({'success': False, 'error': 'Senha atual incorreta.'}, status=400)

    try:
        validate_password(new_password, user=user)
    except Exception as e:
        errors = getattr(e, 'messages', None)
        msg = errors[0] if errors else 'Senha nova inválida.'
        return JsonResponse({'success': False, 'error': msg}, status=400)

    user.set_password(new_password)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)

    return JsonResponse({'success': True, 'message': 'Senha alterada com sucesso.'})


@require_POST
def api_reset_password_totp(request):
    """Reseta a senha a partir do código do autenticador (TOTP) registrado.

    Espera JSON:
    - username (ou email)
    - otp_code (6 dígitos)
    - new_password
    - confirm_password
    """
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    identifier = (data.get('username') or '').strip()
    otp_code = (data.get('otp_code') or '').strip().replace(' ', '')
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not identifier or not otp_code or not new_password or not confirm_password:
        return JsonResponse({'success': False, 'error': 'Preencha todos os campos.'}, status=400)

    if new_password != confirm_password:
        return JsonResponse({'success': False, 'error': 'As senhas novas não conferem.'}, status=400)

    if not otp_code.isdigit() or len(otp_code) != 6:
        return JsonResponse({'success': False, 'error': 'Código inválido. Use 6 dígitos.'}, status=400)

    User = get_user_model()

    user = None
    if '@' in identifier:
        user = User.objects.filter(email__iexact=identifier, is_active=True).first()
    if user is None:
        user = User.objects.filter(username__iexact=identifier, is_active=True).first()

    if user is None:
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    if TOTPDevice is None:
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    devices = TOTPDevice.objects.filter(user=user, confirmed=True)
    if not devices.exists():
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    token_int = int(otp_code)
    is_valid = False
    for device in devices:
        try:
            if device.verify_token(token_int):
                is_valid = True
                break
        except Exception:
            continue

    if not is_valid:
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    try:
        validate_password(new_password, user=user)
    except Exception as e:
        errors = getattr(e, 'messages', None)
        msg = errors[0] if errors else 'Senha nova inválida.'
        return JsonResponse({'success': False, 'error': msg}, status=400)

    user.set_password(new_password)
    user.save(update_fields=['password'])

    return JsonResponse({'success': True, 'message': 'Senha redefinida com sucesso. Você já pode entrar.'})


# ==============================================================================
# DOWNLOAD DE TEMPLATES
# ==============================================================================

@login_required
def dl_template_instr(request):
    """Template para importação de instrumentos com exemplos."""
    from datetime import date, timedelta
    
    exemplo_data = {
        "TAG": ["INS-001", "INS-002", "INS-003"],
        "EQUIPAMENTO": ["Paquímetro Digital", "Micrômetro", "Termômetro Digital"],
        "STATUS": ["ATIVO", "ATIVO", "INATIVO"],
        "FABRICANTE": ["Mitutoyo", "Starrett", "Fluke"],
        "MODELO": ["CD-6", "436B", "51-2"],
        "N SERIE": ["123456", "789012", "345678"],
        "SETOR": ["PRODUÇÃO", "QUALIDADE", "LABORATÓRIO"],
        "LOCALIZACAO": ["Sala 01", "Sala 02", "Sala 03"],
        "FREQUENCIA_MESES": ["12", "12", "6"],
        "DATA_ULTIMA_CALIBRACAO": [
            (date.today() - timedelta(days=30)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=60)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=180)).strftime("%d/%m/%Y"),
        ],
        "FAIXA": ["0-150", "0-25", "-50 a 50"],
        "UNIDADE": ["mm", "mm", "°C"],
    }
    
    df = pd.DataFrame(exemplo_data)
    return dl_df(df, "template_instrumentos_v2.xlsx")


@login_required
def dl_template_colab(request):
    """Template para importação de colaboradores com exemplos."""
    return dl_df(
        pd.DataFrame(
            {
                "MATRICULA": ["100", "101", "102"],
                "NOME": ["João Silva", "Maria Santos", "Pedro Costa"],
                "CPF": ["123.456.789-00", "987.654.321-11", "555.666.777-88"],
                "CARGO": ["Operador", "Supervisor", "Gerente"],
                "GRUPO": ["OPERAÇÃO", "SUPERVISÃO", "GESTÃO"],
                "SETOR": ["PRODUÇÃO", "QUALIDADE", "PRODUÇÃO"],
                "CC": ["100", "200", "300"],
                "TURNO": ["INTEGRAL", "INTEGRAL", "INTEGRAL"],
                "STATUS": ["ATIVO", "ATIVO", "AFASTADO"],
                "MAT_LIDER": ["999", "999", "999"],
                "MAT_SUPERVISOR": ["888", "888", "888"],
                "MAT_GERENTE": ["777", "777", "777"],
            }
        ),
        "template_colaboradores.xlsx",
    )


@login_required
def dl_template_hierarquia(request):
    """Template para importação de hierarquia com exemplos."""
    return dl_df(
        pd.DataFrame(
            {
                "SETOR": ["PRODUÇÃO", "QUALIDADE", "LABORATÓRIO"],
                "TURNO": ["TURNO 1", "TURNO 1", "INTEGRAL"],
                "MAT_LIDER": ["100", "101", "102"],
                "MAT_SUPERVISOR": ["103", "104", "105"],
                "MAT_GERENTE": ["106", "106", "106"],
                "MAT_DIRETOR": ["999", "999", "999"],
            }
        ),
        "template_hierarquia.xlsx",
    )


@login_required
def dl_template_historico(request):
    """Template para importação de históricos de calibração com exemplos."""
    hoje = date.today()
    df = pd.DataFrame(
        {
            "TAG": ["INS-001", "INS-002", "INS-003"],
            "FAIXA": ["0-100", "0-50", "-10 a 50"],
            "UNIDADE DE MEDIDA": ["mm", "°C", "mV"],
            "DATA CALIBRAÇÃO": [
                (hoje - timedelta(days=30)).strftime("%d/%m/%Y"),
                (hoje - timedelta(days=60)).strftime("%d/%m/%Y"),
                (hoje - timedelta(days=90)).strftime("%d/%m/%Y"),
            ],
            "DATA APROVAÇÃO": [
                (hoje - timedelta(days=29)).strftime("%d/%m/%Y"),
                (hoje - timedelta(days=59)).strftime("%d/%m/%Y"),
                (hoje - timedelta(days=89)).strftime("%d/%m/%Y"),
            ],
            "N CERTIFICADO": ["CERT-2025-001", "CERT-2025-002", "CERT-2025-003"],
            "CAMINHO DO CERTIFICADO": ["", "", ""],
            "ERRO ENCONTRADO": ["0,50", "0,30", "0,80"],
            "INCERTEZA": ["0,20", "0,15", "0,40"],
            "TOLERANCIA PROCESSO (+/-)": ["1,00", "0,50", "2,00"],
            "RBC (SIM/NAO)": ["SIM", "NAO", "SIM"],
            "RESULTADO": ["APROVADO", "CONDICIONAL", "REPROVADO"],
            "FORNECEDOR": ["Laboratório XYZ", "Laboratório ABC", "Laboratório XYZ"],
            "RESPONSÁVEL": ["João Silva", "Maria Santos", "Pedro Costa"],
            "OBSERVAÇÕES": [
                "Calibração OK",
                "Atenção à próxima data",
                "Fora da tolerância",
            ],
        }
    )
    return dl_df(df, "template_historico.xlsx")


@login_required
def dl_template_ferias(request):
    """Template para importação de férias com exemplos."""
    from datetime import date, timedelta
    
    hoje = date.today()
    df = pd.DataFrame(
        {
            "MATRICULA": ["100", "101", "102"],
            "AQUISITIVO_INICIO": [
                "01/01/2024",
                "01/01/2024",
                "01/06/2024",
            ],
            "AQUISITIVO_FIM": [
                "31/12/2024",
                "31/12/2024",
                "31/05/2025",
            ],
            "DATA_INICIO": [
                (hoje + timedelta(days=30)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=60)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=90)).strftime("%d/%m/%Y"),
            ],
            "DATA_FIM": [
                (hoje + timedelta(days=45)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=75)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=105)).strftime("%d/%m/%Y"),
            ],
            "STATUS": ["PROGRAMADAS", "GOZADAS", "PROGRAMADAS"],
        }
    )
    return dl_df(df, "template_ferias.xlsx")


@login_required
def dl_template_categorias(request):
    """Template para importação de categorias."""
    df = pd.DataFrame(
        {
            "nome": ["PAQUIMETROS", "MICROMETROS", "TORQUIMETROS"],
            "descricao": [
                "Instrumentos do tipo paquímetro",
                "Instrumentos do tipo micrômetro",
                "Instrumentos para torque",
            ],
            "unidade_sigla": ["mm", "mm", "Nm"],
        }
    )
    return dl_df(df, "template_categorias.xlsx")


@login_required
def dl_template_procedimentos(request):
    """Template para importação de procedimentos."""
    cols = [
        'no', 'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
        'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
        'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
    ]
    exemplo = {
        'no': ['1'],
        'codigo': ['POP.001'],
        'nome': ['EXEMPLO DE PROCEDIMENTO'],
        'descricao': ['Objetivo ou função do procedimento'],
        'pasta': ['QUALIDADE'],
        'classificacao': ['POP'],
        'autor': ['João da Silva'],
        'numero_revisao': ['01'],
        'ultima_revisao': ['01/10/2025'],
        'data_aprovacao': ['05/10/2025'],
        'proxima_revisao': ['05/10/2026'],
        'data_validade': ['05/10/2026'],
        'documentos_controlados': ['Sim'],
        'matriz': ['Matriz A'],
        'sub_area': ['Subárea 1'],
    }
    df = pd.DataFrame({col: exemplo.get(col, ['']) for col in cols})
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r['Content-Disposition'] = 'attachment; filename="template_procedimentos.xlsx"'
    return r


@login_required
def dl_template_colab_dados(request):
    """Exporta dados completos dos colaboradores ativos."""
    # Define permissão para visualizar salário
    colab = None
    try:
        colab = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    can_see_salary = False
    if request.user.is_superuser or request.user.is_staff:
        can_see_salary = True
    elif colab:
        if colab.setor and "RH" in colab.setor.nome.upper():
            can_see_salary = True

    # Busca colaboradores ativos
    qs = Colaborador.objects.filter(is_active=True).select_related(
        "setor", "centro_custo", "lider", "supervisor", "gerente"
    ).order_by("nome_completo")

    # Monta dados
    data = []
    for colab in qs:
        data.append(
            {
                "MATRICULA": colab.matricula,
                "NOME": colab.nome_completo,
                "CPF": colab.cpf or "",
                "CARGO": colab.cargo or "",
                "GRUPO": colab.grupo or "Geral",
                "SETOR": colab.setor.nome if colab.setor else "",
                "CC": colab.centro_custo.codigo if colab.centro_custo else "",
                "TURNO": colab.get_turno_display(),
                "TURNO_CODIGO": colab.turno,
                "STATUS": "ATIVO",
                "MAT_LIDER": colab.lider.matricula if colab.lider else "",
                "NOME_LIDER": colab.lider.nome_completo if colab.lider else "",
                "MAT_SUPERVISOR": colab.supervisor.matricula if colab.supervisor else "",
                "NOME_SUPERVISOR": colab.supervisor.nome_completo if colab.supervisor else "",
                "MAT_GERENTE": colab.gerente.matricula if colab.gerente else "",
                "NOME_GERENTE": colab.gerente.nome_completo if colab.gerente else "",
                "EM_FERIAS": "SIM" if colab.em_ferias else "NÃO",
                "SALARIO": (float(colab.salario) if (can_see_salary and colab.salario) else ""),
            }
        )

    df = pd.DataFrame(data)
    fname = f"colaboradores_export_{date.today().strftime('%Y%m%d')}.xlsx"

    b = io.BytesIO()
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)

    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


# ==============================================================================
# GERENCIAMENTO DE JOBS DE IMPORTAÇÃO
# ==============================================================================

@login_required
def import_jobs_view(request):
    """Lista jobs de importação com filtros opcionais."""
    try:
        status = (request.GET.get('status') or '').upper()
        job_type = (request.GET.get('type') or '').upper()
        qs = ImportJob.objects.all()
        
        if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
            qs = qs.filter(status=status)
        if job_type:
            qs = qs.filter(job_type__iexact=job_type)
        
        jobs = list(qs.order_by('-created_at')[:100])
        
        # Prepara dados para exibição
        prepared = []
        for j in jobs:
            summary = j.result or ''
            samples = []
            try:
                if summary and '| Samples:' in summary:
                    parts = summary.split('| Samples:')
                    summary = parts[0].strip()
                    samples_str = parts[1].strip() if len(parts) > 1 else ''
                    if samples_str:
                        samples = [s.strip() for s in samples_str.split(',') if s.strip()]
            except Exception:
                samples = []
            
            prepared.append({
                'id': j.id,
                'job_type': j.job_type,
                'filename': j.filename,
                'status': j.status,
                'result_summary': summary,
                'result_samples': samples,
                'created_at': j.created_at,
                'updated_at': j.updated_at,
                'filepath': j.filepath,
            })
        
        return render(request, 'shared/imports/import_jobs.html', {
            'jobs': prepared,
            'status': status,
            'job_type': job_type,
        })
    except Exception as e:
        return HttpResponse(f"<pre>Falha ao carregar import-jobs: {str(e)}</pre>", 
                          content_type="text/html", status=200)


@login_required
def import_jobs_json_view(request):
    """Retorna jobs de importação em JSON."""
    status = (request.GET.get('status') or '').upper()
    job_type = (request.GET.get('type') or '').upper()
    qs = ImportJob.objects.all()
    
    if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
        qs = qs.filter(status=status)
    if job_type:
        qs = qs.filter(job_type__iexact=job_type)
    
    jobs = qs.order_by('-created_at')[:100]
    data = []
    for j in jobs:
        data.append({
            'id': str(j.id),
            'job_type': j.job_type,
            'filename': j.filename,
            'status': j.status,
            'result': j.result,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'updated_at': j.updated_at.isoformat() if j.updated_at else None,
            'filepath': j.filepath,
        })
    return JsonResponse({'jobs': data})


@login_required
def retry_import_job_view(request, job_id):
    """Reprocessa um job de importação falho."""
    from qms.tasks import (
        import_instruments_task, import_historico_task, import_colab_task,
        import_hierarquia_task, import_ferias_task
    )
    
    job = get_object_or_404(ImportJob, id=job_id)
    if not job.filepath:
        messages.error(request, "Este job não tem arquivo associado para reprocessar.")
        return redirect('import_jobs')

    try:
        if job.job_type == 'INSTRUMENTOS':
            try:
                import_instruments_task.delay(str(job.id), job.filepath)
            except Exception:
                import_instruments_task(job.id, job.filepath)
        elif job.job_type == 'HISTORICO':
            try:
                import_historico_task.delay(str(job.id), job.filepath)
            except Exception:
                import_historico_task(job.id, job.filepath)
        elif job.job_type == 'RH_COLAB':
            try:
                import_colab_task.delay(str(job.id), job.filepath)
            except Exception:
                import_colab_task(job.id, job.filepath)
        elif job.job_type == 'RH_HIERARQUIA':
            try:
                import_hierarquia_task.delay(str(job.id), job.filepath)
            except Exception:
                import_hierarquia_task(job.id, job.filepath)
        elif job.job_type == 'RH_FERIAS':
            try:
                import_ferias_task.delay(str(job.id), job.filepath)
            except Exception:
                import_ferias_task(job.id, job.filepath)
        else:
            messages.error(request, "Tipo de job não suportado para retry.")
            return redirect('import_jobs')
        
        messages.success(request, f"Reprocessando job {job.id} ({job.job_type}).")
    except Exception as e:
        messages.error(request, f"Falha ao reprocessar: {e}")
    
    return redirect('import_jobs')


# ==============================================================================
# ADMIN UTILITIES
# ==============================================================================

@login_required
def seed_demo_view(request):
    """Dispara seed de dados demo (apenas para staff)."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('dashboard')
    
    try:
        call_command('seed_demo')
        messages.success(request, 'Base de demonstração carregada com sucesso!')
    except Exception as e:
        messages.error(request, f'Falha ao gerar dados de demonstração: {e}')
    
    return redirect('modulo_rh')


@login_required
def fix_historico_proxima_view(request):
    """Recalcula datas de próxima calibração (apenas para staff)."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('dashboard')
    
    try:
        recalc = bool(request.GET.get('recalc'))
        call_command('fix_historico_proxima', recalc=recalc)
        messages.success(request, 'Recalculo de próxima calibração concluído!')
    except Exception as e:
        messages.error(request, f'Falha no recalculo: {e}')
    
    return redirect('modulo_metrologia')


@csrf_exempt
@require_GET
def run_cron_tasks(request):
    """
    HTTP endpoint to trigger periodic tasks in serverless environment (Vercel).
    Protected by CRON_SECRET token via Authorization Header (Bearer) or secret query param.
    """
    secret = request.GET.get('secret')
    auth_header = request.headers.get('authorization')
    expected_secret = os.getenv('CRON_SECRET')
    
    authorized = False
    if expected_secret:
        if secret == expected_secret:
            authorized = True
        elif auth_header == f"Bearer {expected_secret}":
            authorized = True
            
    if not authorized:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        
    results = {}
    
    # 1. Update status of vacations
    try:
        from rh.tasks.ferias_tasks import atualizar_status_ferias_logic, sincronizar_em_ferias
        results['ferias_status'] = atualizar_status_ferias_logic()
        results['ferias_sincronizacao'] = sincronizar_em_ferias()
    except Exception as e:
        results['ferias_tasks'] = {'error': str(e)}
        
    return JsonResponse({'success': True, 'results': results})

