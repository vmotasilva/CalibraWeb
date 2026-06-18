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
@login_required
def home_view(request):
    """Página inicial com boas-vindas ao usuário."""
    from shared.notifications import CobrancaItem, get_user_cobrancas_items
    from auditoria.models import RelatorioCompartilhadoAuditoria

    cobrancas_items = get_user_cobrancas_items(request.user)
    total_cobrancas = sum(item.count for item in cobrancas_items)

    now = timezone.now()
    shares_qs = (
        RelatorioCompartilhadoAuditoria.objects.filter(destinatario=request.user, ativo=True)
        .select_related("remetente", "modelo")
        .order_by("-criado_em", "-id")[:12]
    )
    recebidos_relatorios = []
    pendentes_compartilhamento = 0
    for item in shares_qs:
        expirado = bool(item.expira_em and item.expira_em <= now)
        if not expirado and not item.recebido_em:
            pendentes_compartilhamento += 1

        target = reverse("auditoria:registros_por_modelo_compartilhado", args=[item.modelo_id])
        url = f"{target}?{urlencode({'share_token': item.token})}"

        recebidos_relatorios.append(
            {
                "id": item.id,
                "modelo_nome": item.modelo.nome,
                "remetente": item.remetente,
                "inicio": item.inicio,
                "fim": item.fim,
                "subcategoria": (item.subcategoria or "").strip(),
                "criado_em": item.criado_em,
                "recebido_em": item.recebido_em,
                "expira_em": item.expira_em,
                "expirado": expirado,
                "url": url,
            }
        )

    has_auditoria_item = any(getattr(i, "key", "") == "auditoria" for i in cobrancas_items)
    if has_auditoria_item:
        relatorios_url = "#relatorios-compartilhados" if recebidos_relatorios else reverse("auditoria:modulo")
        cobrancas_items.append(
            CobrancaItem(
                key="auditoria_relatorios_compartilhados",
                label="Relatórios compartilhados (recebidos)",
                count=int(pendentes_compartilhamento),
                url=relatorios_url,
                section="Auditoria",
            )
        )
        total_cobrancas += int(pendentes_compartilhamento)

    return render(
        request,
        "shared/home.html",
        {
            "cobrancas_items": cobrancas_items,
            "total_cobrancas": total_cobrancas,
            "recebidos_relatorios": recebidos_relatorios,
            "pendentes_compartilhamento": pendentes_compartilhamento,
        },
    )


def _hub_safe_reverse(view_name):
    try:
        return reverse(view_name)
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


def _hub_get_laboratorio_open_count():
    try:
        from laboratorio.models import OcorrenciaLaboratorio

        return OcorrenciaLaboratorio.objects.filter(data_encerramento__isnull=True).count()
    except Exception:
        return 0


def _hub_build_action(user, module_key, module_title, action_config):
    view_name = action_config["view_name"]
    if not _hub_can_access(user, module_key, view_name):
        return None

    url = _hub_safe_reverse(view_name)
    if not url:
        return None

    return {
        "id": action_config["id"],
        "label": action_config["label"],
        "description": action_config["description"],
        "icon": action_config["icon"],
        "url": url,
        "module_title": module_title,
    }


@login_required
def hub_view(request):
    laboratorio_open_count = _hub_get_laboratorio_open_count()
    counts = {
        **get_user_cobrancas_counts(request.user),
        "laboratorio_abertas": laboratorio_open_count,
    }

    pending_items = [
        {
            "key": item.key,
            "label": item.label,
            "count": int(item.count or 0),
            "url": item.url,
            "section": item.section,
        }
        for item in get_user_cobrancas_items(request.user)
        if int(item.count or 0) > 0
    ]

    if laboratorio_open_count and _hub_can_access(request.user, "laboratorio", "laboratorio:modulo"):
        pending_items.append(
            {
                "key": "laboratorio_abertas",
                "label": "Laboratório (ocorrências abertas)",
                "count": laboratorio_open_count,
                "url": _hub_safe_reverse("laboratorio:modulo"),
                "section": "Laboratório",
            }
        )

    pending_items = sorted(
        pending_items,
        key=lambda item: (-item["count"], item["section"], item["label"]),
    )[:8]

    module_configs = [
        {
            "id": "laboratorio",
            "title": "Laboratório",
            "module_key": "laboratorio",
            "description": "Ocorrências, dashboards e visão operacional das máquinas do laboratório.",
            "icon": "bi-flask",
            "color": "#1f7a66",
            "hub_view_name": "laboratorio:modulo",
            "pending_keys": ["laboratorio_abertas"],
            "pending_label": "ocorrências abertas",
            "quick_actions": [
                {
                    "id": "laboratorio-nova-ocorrencia",
                    "label": "Nova ocorrência",
                    "description": "Registrar uma ocorrência geral do laboratório.",
                    "icon": "bi-plus-square",
                    "view_name": "laboratorio:ocorrencia_create",
                },
                {
                    "id": "laboratorio-dashboard",
                    "label": "Dashboard do laboratório",
                    "description": "Acompanhar os principais indicadores do módulo.",
                    "icon": "bi-speedometer2",
                    "view_name": "laboratorio:dashboard",
                },
                {
                    "id": "laboratorio-maquinas",
                    "label": "Máquinas",
                    "description": "Consultar o cadastro e histórico das máquinas.",
                    "icon": "bi-gear-wide-connected",
                    "view_name": "maquinas:maquinas_list",
                },
            ],
        },
        {
            "id": "metrologia",
            "title": "Metrologia",
            "module_key": "metrologia",
            "description": "Instrumentos, calibrações e fluxo de solicitações de cotação.",
            "icon": "bi-rulers",
            "color": "#0d6efd",
            "hub_view_name": "modulo_metrologia",
            "pending_keys": ["metrologia", "cotacoes"],
            "pending_label": "alertas operacionais",
            "quick_actions": [
                {
                    "id": "metrologia-lista-instrumentos",
                    "label": "Lista de instrumentos",
                    "description": "Abrir a visão geral de instrumentos e calibrações.",
                    "icon": "bi-list-check",
                    "view_name": "modulo_metrologia",
                },
                {
                    "id": "metrologia-nova-solicitacao",
                    "label": "Nova solicitação",
                    "description": "Iniciar uma nova solicitação de cotação.",
                    "icon": "bi-clipboard-plus",
                    "view_name": "metrologia:solicitacao_create",
                },
                {
                    "id": "metrologia-cotacoes",
                    "label": "Cotações",
                    "description": "Acompanhar solicitações e seus prazos.",
                    "icon": "bi-cash-stack",
                    "view_name": "metrologia:solicitacao_list",
                },
            ],
        },
        {
            "id": "acoes",
            "title": "Ações",
            "module_key": "acoes",
            "description": "Gerenciamento de ações corretivas, soluções e acompanhamento de prazos.",
            "icon": "bi-check2-square",
            "color": "#bf6b04",
            "hub_view_name": "acoes:dashboard",
            "pending_keys": ["acoes"],
            "pending_label": "ações vencidas",
            "quick_actions": [
                {
                    "id": "acoes-dashboard",
                    "label": "Painel de ações",
                    "description": "Ver o panorama consolidado do módulo.",
                    "icon": "bi-kanban",
                    "view_name": "acoes:dashboard",
                },
                {
                    "id": "acoes-registradas",
                    "label": "Ações registradas",
                    "description": "Listar e filtrar as ações em andamento.",
                    "icon": "bi-card-checklist",
                    "view_name": "acoes:acoes_registradas",
                },
                {
                    "id": "acoes-cadastro",
                    "label": "Cadastro base",
                    "description": "Acessar o cadastro principal do módulo.",
                    "icon": "bi-folder2-open",
                    "view_name": "acoes:listar_acoes",
                },
            ],
        },
        {
            "id": "auditoria",
            "title": "Auditoria",
            "module_key": "auditoria",
            "description": "Execução de auditorias, modelos e acompanhamento mensal das rotinas.",
            "icon": "bi-clipboard-data",
            "color": "#8b5cf6",
            "hub_view_name": "auditoria:dashboard",
            "pending_keys": ["auditoria"],
            "pending_label": "auditorias pendentes",
            "quick_actions": [
                {
                    "id": "auditoria-dashboard",
                    "label": "Dashboard de auditoria",
                    "description": "Visualizar os indicadores e o calendário do módulo.",
                    "icon": "bi-bar-chart-line",
                    "view_name": "auditoria:dashboard",
                },
                {
                    "id": "auditoria-preencher",
                    "label": "Preencher auditoria",
                    "description": "Iniciar um novo registro a partir de um modelo.",
                    "icon": "bi-journal-plus",
                    "view_name": "auditoria:selecionar_modelo_preenchimento",
                },
            ],
        },
        {
            "id": "rh",
            "title": "Pessoas",
            "module_key": "rh",
            "description": "Equipe, férias, lideranças e visão central do quadro de colaboradores.",
            "icon": "bi-people",
            "color": "#0f766e",
            "hub_view_name": "modulo_rh",
            "pending_keys": [],
            "pending_label": "rotinas críticas no radar",
            "quick_actions": [
                {
                    "id": "rh-dashboard",
                    "label": "Quadro de colaboradores",
                    "description": "Abrir a visão principal da equipe.",
                    "icon": "bi-people-fill",
                    "view_name": "modulo_rh",
                },
                {
                    "id": "rh-ferias",
                    "label": "Gestão de férias",
                    "description": "Consultar e programar férias do time.",
                    "icon": "bi-calendar-check",
                    "view_name": "rh:gestao_ferias",
                },
                {
                    "id": "rh-usuarios",
                    "label": "Usuários do sistema",
                    "description": "Administrar acessos e permissões.",
                    "icon": "bi-person-gear",
                    "view_name": "rh:listar_usuarios",
                },
            ],
        },
        {
            "id": "treinamentos",
            "title": "Treinamentos",
            "module_key": "procedures",
            "description": "Matriz de habilidade, demandas e planejamento de treinamentos.",
            "icon": "bi-mortarboard",
            "color": "#2563eb",
            "hub_view_name": "procedures:dashboard_treinamentos",
            "pending_keys": ["trein_matriz", "trein_demanda", "trein_planejamentos"],
            "pending_label": "pendências de treinamento",
            "quick_actions": [
                {
                    "id": "treinamentos-dashboard",
                    "label": "Dashboard de treinamentos",
                    "description": "Visualizar o desempenho e as pendências da equipe.",
                    "icon": "bi-easel2",
                    "view_name": "procedures:dashboard_treinamentos",
                },
                {
                    "id": "treinamentos-validacoes",
                    "label": "Validações pendentes",
                    "description": "Atuar nas validações da matriz de habilidade.",
                    "icon": "bi-patch-check",
                    "view_name": "procedures:validacoes_pendentes",
                },
                {
                    "id": "treinamentos-planejamentos",
                    "label": "Planejamentos",
                    "description": "Acompanhar os treinamentos agendados e atrasados.",
                    "icon": "bi-calendar3",
                    "view_name": "procedures:planejamentos_list",
                },
            ],
        },
        {
            "id": "fornecedores",
            "title": "Fornecedores",
            "module_key": "fornecedores",
            "description": "Cadastro, documentos e avaliações da base de fornecedores.",
            "icon": "bi-truck",
            "color": "#7c3aed",
            "hub_view_name": "fornecedores:fornecedor_list",
            "pending_keys": [],
            "pending_label": "itens acompanhados no hub",
            "quick_actions": [
                {
                    "id": "fornecedores-lista",
                    "label": "Lista de fornecedores",
                    "description": "Consultar a base atual de fornecedores.",
                    "icon": "bi-building",
                    "view_name": "fornecedores:fornecedor_list",
                },
                {
                    "id": "fornecedores-novo",
                    "label": "Novo fornecedor",
                    "description": "Cadastrar um novo fornecedor na base.",
                    "icon": "bi-building-add",
                    "view_name": "fornecedores:fornecedor_create",
                },
            ],
        },
    ]

    modules = []
    quick_actions = []
    seen_action_ids = set()

    for module_config in module_configs:
        if not _hub_can_access(request.user, module_config["module_key"], module_config["hub_view_name"]):
            continue

        module_url = _hub_safe_reverse(module_config["hub_view_name"])
        if not module_url:
            continue

        module_actions = []
        for action_config in module_config["quick_actions"]:
            action = _hub_build_action(
                request.user,
                module_config["module_key"],
                module_config["title"],
                action_config,
            )
            if not action:
                continue

            module_actions.append(action)
            if action["id"] not in seen_action_ids:
                seen_action_ids.add(action["id"])
                quick_actions.append(action)

        pending_count = sum(int(counts.get(key, 0) or 0) for key in module_config["pending_keys"])
        modules.append(
            {
                "id": module_config["id"],
                "title": module_config["title"],
                "description": module_config["description"],
                "icon": module_config["icon"],
                "color": module_config["color"],
                "url": module_url,
                "pending_count": pending_count,
                "status_text": (
                    f"{pending_count} {module_config['pending_label']}"
                    if pending_count
                    else "Sem pendências críticas mapeadas neste momento"
                ),
                "actions": module_actions[:3],
            }
        )

    hub_stats = [
        {
            "label": "Módulos liberados",
            "value": len(modules),
            "detail": "áreas disponíveis para o seu perfil",
        },
        {
            "label": "Pendências ativas",
            "value": int(counts.get("total", 0) or 0) + laboratorio_open_count,
            "detail": "itens que já exigem alguma ação",
        },
        {
            "label": "Ações rápidas",
            "value": len(quick_actions),
            "detail": "atalhos operacionais no hub",
        },
        {
            "label": "Favoritos",
            "value": 0,
            "detail": "atalhos fixados neste navegador",
            "dynamic_id": "hub-favorites-count",
        },
    ]

    return render(
        request,
        "shared/hub.html",
        {
            "hub_stats": hub_stats,
            "pending_items": pending_items,
            "quick_actions": quick_actions,
            "modules": modules,
        },
    )


def dashboard_view(request):
    """Dashboard principal agregando dados de todos os módulos."""
    nome_display = request.user.username
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)

    # Metrologia
    qtd_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=hoje, ativo=True
    ).count()
    qtd_avencer = Instrumento.objects.filter(
        data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True
    ).count()
    lista_urgentes = Instrumento.objects.filter(
        data_proxima_calibracao__lte=trinta_dias, ativo=True
    ).order_by("data_proxima_calibracao")[:5]

    # Procurements
    qtd_pendentes = SolicitacaoInstrumento.objects.filter(status="PENDENTE").count()

    ctx = {
        "nome_display": nome_display,
        "qtd_vencidos": qtd_vencidos,
        "qtd_avencer": qtd_avencer,
        "lista_urgentes": lista_urgentes,
        "qtd_cotacoes": ProcessoCotacao.objects.filter(status="ABERTO").count(),
        "qtd_pendentes": qtd_pendentes,
        "today": hoje,
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
    
    # 1. Update status of delayed actions
    try:
        from acoes.tasks import atualizar_status_acoes_atrasadas
        results['acoes_atrasadas'] = atualizar_status_acoes_atrasadas()
    except Exception as e:
        results['acoes_atrasadas'] = {'error': str(e)}
        
    # 2. Update status of vacations
    try:
        from rh.tasks.ferias_tasks import atualizar_status_ferias_logic, sincronizar_em_ferias
        results['ferias_status'] = atualizar_status_ferias_logic()
        results['ferias_sincronizacao'] = sincronizar_em_ferias()
    except Exception as e:
        results['ferias_tasks'] = {'error': str(e)}
        
    return JsonResponse({'success': True, 'results': results})

