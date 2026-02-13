# -*- coding: utf-8 -*-
from datetime import datetime
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from openpyxl import load_workbook, Workbook

from acoes.forms import ImportacaoControleRegistrosForm
from acoes.models import AcaoCorretiva, Solucao, PlanoAcao, LinhaAcao, KPIOpcao
from rh.models import Colaborador


TEMPLATE_HEADERS = [
    "Data de abertura",
    "Ano",
    "Unidade",
    "Nº do Registro",
    "Tipo de Solução",
    "Origem do Problema",
    "Descrição da NC e/ou Melhoria",
    "Causa Raiz",
    "Responsável",
    "Observação",
    "Link do registro",
    "Data de Fechamento Programada",
    "Data Fechamento",
    "Status",
]


HEADER_MAP = {
    "datadeabertura": "data_abertura",
    "ano": "ano",
    "unidade": "unidade",
    "ndoregistro": "numero_registro",
    "tipodesoluo": "tipo_solucao",
    "origemdoproblema": "origem",
    "descriodanceoumelhoria": "descricao",
    "causaraiz": "causa_raiz",
    "responsvel": "responsavel_matricula",
    "observao": "observacoes",
    "linkdoregistro": "link_registro",
    "datadefechamentoprogramada": "data_vencimento",
    "datafechamento": "data_conclusao",
    "status": "status",
}

SOLUCAO_TIPO_MAP = {
    "plano de acao": "plano_acao",
    "planoacao": "plano_acao",
    "plano_acao": "plano_acao",
    "a3": "a3",
    "8d": "8d",
    "rnc": "rnc",
    "gestao de mudanca": "gestao_mudanca",
    "gestaodemudanca": "gestao_mudanca",
    "gestao_mudanca": "gestao_mudanca",
    "revisao gerencial": "revisao_gerencial",
    "revisaogerencial": "revisao_gerencial",
    "revisao_gerencial": "revisao_gerencial",
}


SOLUCAO_STATUS_MAP = {
    "planejamento": "planejamento",
    "analise": "analise",
    "implementacao": "implementacao",
    "validacao": "validacao",
    "encerrada": "encerrada",
}


ACAO_STATUS_MAP = {
    "aberta": "aberta",
    "em progresso": "em_progresso",
    "em_progresso": "em_progresso",
    "concluida": "concluida",
    "cancelada": "cancelada",
}


ACAO_TIPO_MAP = {
    "corretiva": "corretiva",
    "preventiva": "preventiva",
}


ACAO_TIPO_SOLUCAO_MAP = {
    "corretiva": "corretiva",
    "preventiva": "preventiva",
    "melhoria": "melhoria",
}


ACAO_PRIORIDADE_MAP = {
    "baixa": "baixa",
    "media": "media",
    "alta": "alta",
    "critica": "critica",
}


def normalize_header(value):
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def parse_bool(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "sim", "s", "yes"}:
        return True
    if text in {"0", "false", "nao", "n", "no"}:
        return False
    return default


def parse_date(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value.date()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def resolve_choice(value, mapping, default=None):
    if value is None or value == "":
        return default
    key = str(value).strip().lower()
    return mapping.get(key, default)


def get_colaborador_by_matricula(matricula):
    matricula = str(matricula).strip()
    if not matricula:
        return None
    return Colaborador.objects.filter(matricula=matricula).first()


def build_template_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "Controles"
    ws.append(TEMPLATE_HEADERS)
    ws.append([
        "13/02/2026",
        2026,
        "Tecnolens",
        "PA-TEC-001/2026",
        "Melhoria",
        "Processo",
        "Implementar novo sistema de gestao",
        "Necessidade de otimizacao",
        "202",
        "Observacoes gerenciais",
        "https://tecnolens.sharepoint.com/...",
        "31/12/2026",
        "",
        "aberta",
    ])
    return wb


@login_required
@require_http_methods(["GET"])
def download_template_controle_registros(request):
    wb = build_template_workbook()
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=template_controle_registros.xlsx"
    wb.save(response)
    return response


@login_required
@require_http_methods(["GET", "POST"])
def importar_controle_registros(request):
    if request.method == "GET":
        form = ImportacaoControleRegistrosForm()
        return render(request, "acoes/importar_controle_registros.html", {"form": form})

    form = ImportacaoControleRegistrosForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Envie uma planilha valida para importacao.")
        return redirect("acoes:importar_controle_registros")

    arquivo = request.FILES.get("arquivo_excel")
    if not arquivo:
        messages.error(request, "Nenhum arquivo foi enviado.")
        return redirect("acoes:importar_controle_registros")

    try:
        wb = load_workbook(filename=arquivo, data_only=True)
        ws = wb.active
    except Exception as exc:
        messages.error(request, f"Erro ao ler a planilha: {exc}")
        return redirect("acoes:importar_controle_registros")

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        messages.error(request, "Planilha vazia.")
        return redirect("acoes:importar_controle_registros")

    header_row = rows[0]
    header_indexes = {}
    for idx, header in enumerate(header_row):
        normalized = normalize_header(header)
        if normalized in HEADER_MAP:
            header_indexes[HEADER_MAP[normalized]] = idx

    required_fields = [
        "numero_registro",
        "descricao",
        "data_vencimento",
    ]
    missing_required = [field for field in required_fields if field not in header_indexes]
    if missing_required:
        messages.error(
            request,
            "Colunas obrigatorias ausentes: " + ", ".join(missing_required),
        )
        return redirect("acoes:importar_controle_registros")

    created = 0
    updated = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue

        def get_cell(field):
            col_idx = header_indexes.get(field)
            if col_idx is None or col_idx >= len(row):
                return None
            return row[col_idx]

        numero_registro = str(get_cell("numero_registro") or "").strip()
        if not numero_registro:
            errors.append(f"Linha {row_idx}: Numero Registro vazio")
            continue

        descricao = str(get_cell("descricao") or "").strip()
        data_vencimento = parse_date(get_cell("data_vencimento"))
        if not descricao or not data_vencimento:
            errors.append(
                f"Linha {row_idx}: Descricao e Data de Vencimento sao obrigatorios"
            )
            continue

        acao_defaults = {
            "descricao": descricao,
            "data_vencimento": data_vencimento,
            "data_abertura": parse_date(get_cell("data_abertura")),
            "unidade": get_cell("unidade") or "",
            "origem": get_cell("origem") or "",
            "causa_raiz": get_cell("causa_raiz") or "",
            "observacoes": get_cell("observacoes") or "",
            "link_registro": get_cell("link_registro") or "",
            "ano": get_cell("ano") or None,
            "tipo_solucao": get_cell("tipo_solucao") or "",
            "data_conclusao": parse_date(get_cell("data_conclusao")),
            "status": get_cell("status") or "aberta",
        }

        responsavel = get_colaborador_by_matricula(get_cell("responsavel_matricula"))
        acao_defaults["responsavel"] = responsavel

        acao, created_flag = AcaoCorretiva.objects.get_or_create(
            numero_registro=numero_registro,
            defaults=acao_defaults,
        )
        if created_flag:
            created += 1
        else:
            for field, value in acao_defaults.items():
                if value is not None and value != "":
                    setattr(acao, field, value)
            acao.save()
            updated += 1

    if errors:
        messages.warning(
            request,
            f"Importacao concluida com avisos. Criadas: {created}, Atualizadas: {updated}, Erros: {len(errors)}",
        )
        for erro in errors[:8]:
            messages.info(request, erro)
        if len(errors) > 8:
            messages.info(request, f"... e mais {len(errors) - 8} erros")
    else:
        messages.success(request, f"Importacao concluida! Criadas: {created}, Atualizadas: {updated}")

    return redirect("acoes:listar_solucoes")


# ============================================================================
# Segunda Importacao: PlanoAcao + LinhaAcao
# ============================================================================

PLANO_ACAO_TEMPLATE_HEADERS = [
    "Solucao Titulo",
    "Numero Acao",
    "Descricao Acao",
    "Classificacao",
    "Status Acao",
    "Responsavel Matricula",
    "Data Primeira Deadline",
    "Data Deadline",
    "Data Conclusao",
    "KPI Opcao",
    "Meta Esperada",
    "Acao Eficaz",
    "Observacoes",
]


PLANO_ACAO_HEADER_MAP = {
    "solucaotitulo": "solucao_titulo",
    "numeroacao": "numero_acao",
    "descricaoacao": "descricao_acao",
    "classificacao": "classificacao",
    "statusacao": "status_acao",
    "responsavelmatricula": "responsavel_matricula",
    "dataprimeiradeadline": "data_primeira_deadline",
    "datadeadline": "data_deadline",
    "dataconclusao": "data_conclusao",
    "kpiopcao": "kpi_opcao",
    "metaesperada": "meta_esperada",
    "acaoeficaz": "acao_eficaz",
    "observacoes": "observacoes",
}


LINHA_ACAO_STATUS_MAP = {
    "planejada": "planejada",
    "em andamento": "em_andamento",
    "em_andamento": "em_andamento",
    "completa": "completa",
    "cancelada": "cancelada",
}


LINHA_ACAO_CLASSIFICACAO_MAP = {
    "corretiva": "corretiva",
    "preventiva": "preventiva",
    "melhoria": "melhoria",
}


def build_plano_acao_template_workbook():
    """Cria workbook com 2 abas: Controles e Ações"""
    wb = Workbook()
    
    # Primeira aba: Controles (para referência)
    ws_controles = wb.active
    ws_controles.title = "Controles"
    ws_controles.append(TEMPLATE_HEADERS)
    ws_controles.append([
        "PA-TEC-001/2026",
        2026,
        "Unidade X",
        "Titulo da acao",
        "Descricao da acao",
        "corretiva",
        "corretiva",
        "media",
        "Processo",
        "Causa raiz exemplo",
        "aberta",
        "2026-02-10",
        "2026-03-10",
        "",
        "202",
        "202",
        "Meta/objetivo",
        "",
        "",
        "https://exemplo.com",
        "true",
        "Plano de Acao - PA-TEC-001/2026",
        "Descricao da solucao",
        "plano_acao",
        "planejamento",
        "2026-02-10",
        "",
        "202",
        "true",
    ])
    
    # Segunda aba: Ações
    ws_acoes = wb.create_sheet("Acoes")
    ws_acoes.append(PLANO_ACAO_TEMPLATE_HEADERS)
    ws_acoes.append([
        "Plano de Acao - PA-TEC-001/2026",
        "001",
        "Implantar novo processo",
        "corretiva",
        "planejada",
        "202",
        "2026-03-10",
        "2026-04-10",
        "",
        "Tempo de ciclo",
        "Reduzir em 25%",
        False,
        "Acao de exemplo",
    ])
    
    return wb


@login_required
@require_http_methods(["GET"])
def download_template_plano_acao(request):
    wb = build_plano_acao_template_workbook()
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=template_plano_acao.xlsx"
    wb.save(response)
    return response


@login_required
@require_http_methods(["GET", "POST"])
def importar_plano_acao(request):
    """
    Importa PlanoAcao + LinhaAcao de Excel com 2 abas:
    - Aba 'Acoes': Contem as linhas de acao
    Usa Titulo da Solucao para vincular a uma Solucao existente
    """
    if request.method == "GET":
        form = ImportacaoControleRegistrosForm()
        return render(request, "acoes/importar_plano_acao.html", {"form": form})

    form = ImportacaoControleRegistrosForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Envie uma planilha valida para importacao.")
        return redirect("acoes:importar_plano_acao")

    arquivo = request.FILES.get("arquivo_excel")
    if not arquivo:
        messages.error(request, "Nenhum arquivo foi enviado.")
        return redirect("acoes:importar_plano_acao")

    try:
        wb = load_workbook(filename=arquivo, data_only=True)
    except Exception as exc:
        messages.error(request, f"Erro ao ler a planilha: {exc}")
        return redirect("acoes:importar_plano_acao")

    # Procura pela aba "Acoes"
    ws = None
    for sheet_name in wb.sheetnames:
        if normalize_header(sheet_name) == normalize_header("Acoes"):
            ws = wb[sheet_name]
            break
    
    if not ws:
        messages.error(request, "Planilha nao contem aba 'Acoes'.")
        return redirect("acoes:importar_plano_acao")

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        messages.error(request, "Aba 'Acoes' vazia.")
        return redirect("acoes:importar_plano_acao")

    header_row = rows[0]
    header_indexes = {}
    for idx, header in enumerate(header_row):
        normalized = normalize_header(header)
        if normalized in PLANO_ACAO_HEADER_MAP:
            header_indexes[PLANO_ACAO_HEADER_MAP[normalized]] = idx

    required_fields = [
        "solucao_titulo",
        "numero_acao",
        "descricao_acao",
        "status_acao",
    ]
    missing_required = [field for field in required_fields if field not in header_indexes]
    if missing_required:
        messages.error(
            request,
            "Colunas obrigatorias ausentes na aba 'Acoes': " + ", ".join(missing_required),
        )
        return redirect("acoes:importar_plano_acao")

    criadas = 0
    atualizadas = 0
    errors = []
    plano_acao_map = {}  # Mapear solucao_titulo -> PlanoAcao

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue

        def get_cell(field):
            col_idx = header_indexes.get(field)
            if col_idx is None or col_idx >= len(row):
                return None
            return row[col_idx]

        # Busca a Solucao existente pelo titulo
        solucao_titulo = str(get_cell("solucao_titulo") or "").strip()
        if not solucao_titulo:
            errors.append(f"Linha {row_idx} (Acoes): Solucao Titulo obrigatorio")
            continue

        solucao = Solucao.objects.filter(titulo=solucao_titulo).first()
        if not solucao:
            errors.append(f"Linha {row_idx} (Acoes): Solucao '{solucao_titulo}' nao encontrada")
            continue

        # Cria ou recupera PlanoAcao para esta solucao (apenas um por solucao)
        if solucao_titulo not in plano_acao_map:
            plano_acao, _ = PlanoAcao.objects.get_or_create(solucao=solucao)
            plano_acao_map[solucao_titulo] = plano_acao
        else:
            plano_acao = plano_acao_map[solucao_titulo]

        numero_acao = str(get_cell("numero_acao") or "").strip()
        descricao_acao = str(get_cell("descricao_acao") or "").strip()
        if not numero_acao or not descricao_acao:
            errors.append(f"Linha {row_idx} (Acoes): Numero e Descricao da acao obrigatorios")
            continue

        status_raw = get_cell("status_acao")
        status = resolve_choice(status_raw, LINHA_ACAO_STATUS_MAP, "planejada")

        linha_acao_defaults = {
            "numero": numero_acao,
            "descricao": descricao_acao,
            "classificacao": resolve_choice(
                get_cell("classificacao"), LINHA_ACAO_CLASSIFICACAO_MAP, "corretiva"
            ),
            "status": status,
            "data_primeira_deadline": parse_date(get_cell("data_primeira_deadline")),
            "data_deadline": parse_date(get_cell("data_deadline")),
            "data_conclusao": parse_date(get_cell("data_conclusao")),
            "meta_esperada": get_cell("meta_esperada") or "",
            "acao_eficaz": parse_bool(get_cell("acao_eficaz")),
            "observacoes": get_cell("observacoes") or "",
        }

        # Resolvendo Responsavel
        responsavel = get_colaborador_by_matricula(get_cell("responsavel_matricula"))
        if get_cell("responsavel_matricula") and not responsavel:
            errors.append(f"Linha {row_idx} (Acoes): Responsavel matricula nao encontrado")
        linha_acao_defaults["responsavel"] = responsavel

        # Resolvendo KPI
        kpi_nome = str(get_cell("kpi_opcao") or "").strip()
        if kpi_nome:
            kpi = KPIOpcao.objects.filter(nome__iexact=kpi_nome).first()
            if not kpi:
                errors.append(f"Linha {row_idx} (Acoes): KPI '{kpi_nome}' nao encontrado")
            else:
                linha_acao_defaults["kpi"] = kpi

        # Get or create LinhaAcao by numero (única por PlanoAcao)
        linha_acao, created_flag = LinhaAcao.objects.get_or_create(
            plano_acao=plano_acao,
            numero=numero_acao,
            defaults=linha_acao_defaults,
        )

        if created_flag:
            criadas += 1
        else:
            # Atualiza campos existentes
            for field, value in linha_acao_defaults.items():
                if value is not None and value != "":
                    setattr(linha_acao, field, value)
            linha_acao.save()
            atualizadas += 1

    if errors:
        messages.warning(
            request,
            f"Importacao concluida com avisos. Criadas: {criadas}, Atualizadas: {atualizadas}, Erros: {len(errors)}",
        )
        for erro in errors[:8]:
            messages.info(request, erro)
        if len(errors) > 8:
            messages.info(request, f"... e mais {len(errors) - 8} erros")
    else:
        messages.success(request, f"Importacao concluida! Criadas: {criadas}, Atualizadas: {atualizadas}")

    return redirect("acoes:listar_solucoes")

