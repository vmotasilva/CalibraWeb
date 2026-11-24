"""Auditoria Livre: auditoria sem norma/checklist, baseada em solicitação de evidência.

O auditor define objetivo/escopo, vai solicitando evidências e direciona cada uma como
Conforme, Não Conformidade, Oportunidade de Melhoria (ou N/A / Pendente).
"""
import io
import json
import re
from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import AuditoriaLivre, ImagemSolicitacaoLivre, SolicitacaoLivre

CLASSIFICACOES = dict(SolicitacaoLivre.CLASSIFICACAO_CHOICES)


def _parse_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _next_url(request, default):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return default


def _imagens_prefetch():
    """Prefetch das fotos sem trazer a coluna base64 (a página usa a URL servida)."""
    return Prefetch("imagens", queryset=ImagemSolicitacaoLivre.objects.defer("arquivo_base64"))


def _serialize_imagem(img):
    return {"id": img.id, "url": img.url, "legenda": img.legenda, "nome": img.nome_arquivo}


def _raiz_id(sol):
    return sol.pai_id or sol.pk


def _grupo_qs(sol):
    """Todas as linhas (itens) da mesma solicitação: a original e os itens extras."""
    raiz = _raiz_id(sol)
    return SolicitacaoLivre.objects.filter(Q(pk=raiz) | Q(pai_id=raiz))


def _serialize(sol):
    return {
        "id": sol.id,
        "topico": sol.topico,
        "solicitacao": sol.solicitacao,
        "evidencia": sol.evidencia,
        "conclusao": sol.conclusao,
        "grau_nc": sol.grau_nc or "",
        "observacao": sol.observacao,
        "capa_status": sol.capa_status,
        "capa_status_display": sol.get_capa_status_display(),
        "imagens": [_serialize_imagem(i) for i in sol.imagens.all()],
    }


# ------------------------------------------------------------------ lista

@login_required
def livre_list(request):
    mostrar_arquivadas = request.GET.get("arquivadas") == "1"
    total_arquivadas = AuditoriaLivre.objects.filter(arquivada=True).count()
    auditorias = list(AuditoriaLivre.objects.filter(arquivada=mostrar_arquivadas))
    for aud in auditorias:
        aud.res = aud.resumo()
    return render(request, "auditoria/livre_list.html", {
        "auditorias": auditorias,
        "mostrar_arquivadas": mostrar_arquivadas,
        "total_arquivadas": total_arquivadas,
    })


# ------------------------------------------------------------- criar/editar

def _salvar_form(request, aud):
    """Aplica o POST na auditoria. Retorna mensagem de erro ou None."""
    titulo = (request.POST.get("titulo") or "").strip()
    data_inicio = _parse_date(request.POST.get("data_inicio"))
    data_fim = _parse_date(request.POST.get("data_fim"))
    if not titulo:
        return "Informe o título da auditoria."
    if not data_inicio:
        return "Informe a data de início."
    if data_fim and data_fim < data_inicio:
        return "A data de fim não pode ser anterior à data de início."

    aud.titulo = titulo
    aud.objetivo = (request.POST.get("objetivo") or "").strip()
    aud.escopo = (request.POST.get("escopo") or "").strip()
    aud.criterio = (request.POST.get("criterio") or "").strip()
    aud.local = (request.POST.get("local") or "").strip()
    aud.auditor_lider = (request.POST.get("auditor_lider") or "").strip()
    aud.auditados = (request.POST.get("auditados") or "").strip()
    aud.data_inicio = data_inicio
    aud.data_fim = data_fim
    if not aud.pk:
        aud.criado_por = request.user
    aud.save()

    ids = [int(i) for i in request.POST.getlist("auditores") if i.isdigit()]
    aud.auditores.set(get_user_model().objects.filter(pk__in=ids, is_active=True))
    return None


def _form_context(aud):
    User = get_user_model()
    return {
        "aud": aud,
        "usuarios": User.objects.filter(is_active=True).order_by("first_name", "username"),
        "selecionados": set(aud.auditores.values_list("pk", flat=True)) if aud and aud.pk else set(),
    }


@login_required
def livre_create(request):
    aud = AuditoriaLivre(data_inicio=date.today())
    if request.method == "POST":
        erro = _salvar_form(request, aud)
        if not erro:
            messages.success(request, "Auditoria livre criada. Comece a solicitar evidências.")
            return redirect("auditoria:livre_execucao", pk=aud.pk)
        messages.error(request, erro)
    ctx = _form_context(aud)
    if request.method == "POST":
        ctx["selecionados"] = {int(i) for i in request.POST.getlist("auditores") if i.isdigit()}
    return render(request, "auditoria/livre_form.html", ctx)


@login_required
def livre_edit(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if request.method == "POST":
        erro = _salvar_form(request, aud)
        if not erro:
            messages.success(request, "Dados da auditoria atualizados.")
            return redirect("auditoria:livre_execucao", pk=aud.pk)
        messages.error(request, erro)
    return render(request, "auditoria/livre_form.html", _form_context(aud))


# ------------------------------------------------------------------ execução

@login_required
def livre_execucao(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if aud.status == "PLANEJADA":
        aud.status = "EM_ANDAMENTO"
        aud.save(update_fields=["status", "atualizado_em"])
    # Agrupa os itens por solicitação, na ordem de criação (itens extras vêm logo após a original).
    grupos, por_raiz = [], {}
    for s in aud.solicitacoes.prefetch_related(_imagens_prefetch()):
        raiz = _raiz_id(s)
        if raiz not in por_raiz:
            por_raiz[raiz] = {"topico": s.topico, "solicitacao": s.solicitacao, "itens": []}
            grupos.append(por_raiz[raiz])
        por_raiz[raiz]["itens"].append(_serialize(s))
    topicos = sorted({g["topico"] for g in grupos if g["topico"]}, key=str.casefold)
    return render(request, "auditoria/livre_execucao.html", {
        "aud": aud,
        "grupos_json": grupos,
        "topicos": topicos,
        "classificacoes": SolicitacaoLivre.CLASSIFICACAO_CHOICES,
        "resumo": aud.resumo(),
    })


# ---------------------------------------------------------------------- API

def _json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _aplicar(sol, data):
    """Aplica campos válidos do payload. Retorna mensagem de erro ou None."""
    if "topico" in data:
        sol.topico = str(data["topico"] or "").strip()[:255]
    if "solicitacao" in data:
        texto = str(data["solicitacao"] or "").strip()
        if not texto:
            return "Descreva a evidência solicitada."
        sol.solicitacao = texto
    if "evidencia" in data:
        sol.evidencia = str(data["evidencia"] or "").strip()
    if "observacao" in data:
        sol.observacao = str(data["observacao"] or "").strip()
    if "conclusao" in data:
        if data["conclusao"] not in CLASSIFICACOES:
            return "Classificação inválida."
        sol.conclusao = data["conclusao"]
    if "grau_nc" in data:
        sol.grau_nc = data["grau_nc"] if data["grau_nc"] in ("MENOR", "MAIOR") else None
    if sol.conclusao != "NC":
        sol.grau_nc = None
    return None


@login_required
@require_POST
def api_livre_sol_create(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    sol = SolicitacaoLivre(auditoria=aud, criado_por=request.user)
    erro = None if str(data.get("solicitacao") or "").strip() else "Descreva a evidência solicitada."
    erro = erro or _aplicar(sol, data)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    sol.ordem = (aud.solicitacoes.aggregate(m=Max("ordem"))["m"] or 0) + 1
    sol.save()
    return JsonResponse({"success": True, "solicitacao": _serialize(sol), "resumo": aud.resumo()})


@login_required
@require_POST
def api_livre_sol_update(request, pk):
    sol = get_object_or_404(SolicitacaoLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    erro = _aplicar(sol, data)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    with transaction.atomic():
        sol.save()
        if "solicitacao" in data or "topico" in data:  # texto e tópico são da solicitação: vale para todos os itens
            _grupo_qs(sol).exclude(pk=sol.pk).update(solicitacao=sol.solicitacao, topico=sol.topico)
    return JsonResponse({"success": True, "solicitacao": _serialize(sol), "resumo": sol.auditoria.resumo()})


@login_required
@require_POST
def api_livre_item_create(request, pk):
    """Adiciona mais um item (nova evidência/classificação) à mesma solicitação de `pk`."""
    base = get_object_or_404(SolicitacaoLivre, pk=pk)
    raiz = base if not base.pai_id else base.pai
    item = SolicitacaoLivre.objects.create(
        auditoria=base.auditoria, pai=raiz, topico=raiz.topico, solicitacao=raiz.solicitacao,
        ordem=raiz.ordem,  # mesma ordem da original: o item fica junto dela na numeração e nos relatórios
        criado_por=request.user,
    )
    return JsonResponse({"success": True, "item": _serialize(item), "resumo": base.auditoria.resumo()})


@login_required
@require_POST
def api_livre_sol_delete(request, pk):
    """Remove um item. Se for a linha original e houver outros itens, o próximo assume o lugar dela."""
    sol = get_object_or_404(SolicitacaoLivre, pk=pk)
    aud = sol.auditoria
    with transaction.atomic():
        if not sol.pai_id:
            extras = list(sol.itens_extras.order_by("id"))
            if extras:
                novo, resto = extras[0], extras[1:]
                SolicitacaoLivre.objects.filter(pk=novo.pk).update(pai=None)
                SolicitacaoLivre.objects.filter(pk__in=[e.pk for e in resto]).update(pai=novo)
        sol.delete()
    return JsonResponse({"success": True, "resumo": aud.resumo()})


@login_required
@require_POST
def api_livre_grupo_delete(request, pk):
    """Remove a solicitação inteira, com todos os itens."""
    sol = get_object_or_404(SolicitacaoLivre, pk=pk)
    aud = sol.auditoria
    _grupo_qs(sol).delete()
    return JsonResponse({"success": True, "resumo": aud.resumo()})


@login_required
@require_POST
def api_livre_conclusao_salvar(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    aud.conclusao_texto = str(data.get("conclusao_texto") or "").strip()
    aud.save(update_fields=["conclusao_texto", "atualizado_em"])
    return JsonResponse({"success": True})


# -------------------------------------------------------- ações da auditoria

@login_required
@require_POST
def livre_toggle_conclusao(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if aud.status == "CONCLUIDA":
        aud.status = "EM_ANDAMENTO"
        messages.success(request, "Auditoria reaberta.")
    else:
        aud.status = "CONCLUIDA"
        if not aud.data_fim:
            aud.data_fim = date.today()
        pendentes = aud.solicitacoes.filter(conclusao="P").count()
        if pendentes:
            messages.warning(
                request,
                f"Auditoria concluída com {pendentes} solicitação(ões) ainda pendente(s) de classificação.",
            )
        else:
            messages.success(request, "Auditoria concluída.")
    aud.save()
    return redirect(_next_url(request, reverse("auditoria:livre_execucao", args=[aud.pk])))


@login_required
@require_POST
def livre_arquivar(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    aud.arquivada = not aud.arquivada
    aud.save(update_fields=["arquivada", "atualizado_em"])
    messages.success(request, "Auditoria arquivada." if aud.arquivada else "Auditoria desarquivada.")
    return redirect(_next_url(request, reverse("auditoria:livre_list")))


@login_required
@require_POST
def livre_delete(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    if not aud.arquivada:
        messages.error(request, "Arquive a auditoria antes de excluí-la.")
        return redirect(_next_url(request, reverse("auditoria:livre_list")))
    aud.delete()
    messages.success(request, "Auditoria excluída.")
    return redirect(reverse("auditoria:livre_list") + "?arquivadas=1")


# ------------------------------------------------------------------- Excel

def _aba_fotos(wb, solicitacoes):
    """Aba "Fotos": cada foto (miniatura) ao lado da evidência a que pertence."""
    import base64
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.styles import Alignment, Font

    com_fotos = [(i, s) for i, s in enumerate(solicitacoes, start=1) if s.imagens.all()]
    if not com_fotos:
        return
    ws = wb.create_sheet("Fotos")
    for col, (titulo, w) in enumerate([("#", 5), ("Evidência solicitada", 45), ("Legenda", 35), ("Foto", 48)], start=1):
        ws.cell(row=1, column=col, value=titulo).font = Font(bold=True)
        ws.column_dimensions[chr(64 + col)].width = w
    linha = 2
    for n, sol in com_fotos:
        ids = [im.id for im in sol.imagens.all()]
        for img in ImagemSolicitacaoLivre.objects.filter(id__in=ids):
            ws.cell(row=linha, column=1, value=n)
            ws.cell(row=linha, column=2, value=sol.solicitacao).alignment = Alignment(wrap_text=True, vertical="top")
            ws.cell(row=linha, column=3, value=img.legenda or img.nome_arquivo).alignment = Alignment(wrap_text=True, vertical="top")
            try:
                xl = XlImage(io.BytesIO(base64.b64decode(img.arquivo_base64)))
                escala = 300 / max(xl.width, xl.height, 1)
                xl.width, xl.height = int(xl.width * escala), int(xl.height * escala)
                ws.add_image(xl, f"D{linha}")
                ws.row_dimensions[linha].height = xl.height * 0.75 + 6
            except Exception:
                ws.cell(row=linha, column=4, value="(foto indisponível)")
            linha += 1


@login_required
def livre_export_excel(request, pk):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    wb = Workbook()

    ws = wb.active
    ws.title = "Resumo"
    resumo = aud.resumo()
    linhas = [
        ("Título", aud.titulo),
        ("Objetivo", aud.objetivo),
        ("Escopo", aud.escopo),
        ("Critério / Referência", aud.criterio),
        ("Local / Setor / Processo", aud.local),
        ("Auditor líder", aud.auditor_lider),
        ("Auditores", ", ".join(u.get_full_name() or u.get_username() for u in aud.auditores.all())),
        ("Auditados", aud.auditados),
        ("Período", f"{aud.data_inicio:%d/%m/%Y}" + (f" a {aud.data_fim:%d/%m/%Y}" if aud.data_fim else "")),
        ("Status", aud.get_status_display()),
        ("", ""),
        ("Total de solicitações", resumo["total"]),
    ] + [(label, resumo[cod]) for cod, label in SolicitacaoLivre.CLASSIFICACAO_CHOICES] + [
        ("", ""),
        ("Conclusão / Parecer", aud.conclusao_texto),
    ]
    for r, (k, v) in enumerate(linhas, start=1):
        ws.cell(row=r, column=1, value=k).font = Font(bold=True)
        c = ws.cell(row=r, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 90

    ws2 = wb.create_sheet("Evidências")
    cab = ["#", "Tópico", "Evidência solicitada", "Evidência apresentada", "Classificação", "Grau NC", "Observação", "Fotos", "Plano de ação", "Responsável", "Prazo"]
    fill = PatternFill("solid", fgColor="1F2937")
    for col, titulo in enumerate(cab, start=1):
        c = ws2.cell(row=1, column=col, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
    cores = {"C": "D1FAE5", "NC": "FEE2E2", "OM": "FEF3C7", "NA": "E5E7EB", "P": "FFFFFF"}
    solicitacoes = list(aud.solicitacoes.prefetch_related(_imagens_prefetch()))
    for i, s in enumerate(solicitacoes, start=1):
        valores = [
            i, s.topico, s.solicitacao, s.evidencia, s.get_conclusao_display(),
            s.get_grau_nc_display() if s.grau_nc else "", s.observacao, len(s.imagens.all()),
            s.get_capa_status_display() if s.conclusao in ("NC", "OM") else "",
            s.capa_responsavel if s.conclusao in ("NC", "OM") else "",
            s.capa_prazo.strftime("%d/%m/%Y") if s.capa_prazo and s.conclusao in ("NC", "OM") else "",
        ]
        for col, v in enumerate(valores, start=1):
            c = ws2.cell(row=i + 1, column=col, value=v)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        ws2.cell(row=i + 1, column=5).fill = PatternFill("solid", fgColor=cores.get(s.conclusao, "FFFFFF"))
    for col, w in enumerate([5, 24, 50, 50, 24, 12, 40, 8, 22, 24, 12], start=1):
        ws2.column_dimensions[get_column_letter(col)].width = w
    ws2.freeze_panes = "A2"
    _aba_fotos(wb, solicitacoes)

    buf = io.BytesIO()
    wb.save(buf)
    nome = re.sub(r"[^a-zA-Z0-9_-]+", "_", aud.titulo).strip("_")[:60] or "auditoria"
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="Auditoria_Livre_{nome}_{aud.pk}.xlsx"'
    return resp


# -------------------------------------------------------------------- fotos

MAX_FOTOS_POR_SOLICITACAO = 12
MAX_BYTES_UPLOAD = 20 * 1024 * 1024  # por arquivo, antes do redimensionamento
LADO_MAXIMO_PX = 1920


def _processar_foto(arquivo):
    """Valida que é imagem de verdade e devolve JPEG redimensionado (bytes). Levanta ValueError."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if arquivo.size > MAX_BYTES_UPLOAD:
        raise ValueError(f"'{arquivo.name}' excede 20 MB.")
    try:
        img = Image.open(arquivo)
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError(f"'{arquivo.name}' não é uma imagem válida.")
    img = ImageOps.exif_transpose(img)  # respeita a orientação da câmera do celular
    if img.mode in ("RGBA", "LA", "P"):
        fundo = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        fundo.paste(rgba, mask=rgba.split()[-1])
        img = fundo
    else:
        img = img.convert("RGB")
    img.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX))
    saida = io.BytesIO()
    img.save(saida, format="JPEG", quality=85, optimize=True)
    return saida.getvalue()


@login_required
@require_POST
def api_livre_imagem_upload(request, pk):
    import base64

    sol = get_object_or_404(SolicitacaoLivre, pk=pk)
    arquivos = request.FILES.getlist("imagem") or request.FILES.getlist("imagens")
    if not arquivos:
        return JsonResponse({"success": False, "error": "Nenhuma imagem enviada."}, status=400)
    legenda = (request.POST.get("legenda") or "").strip()[:255]
    restante = MAX_FOTOS_POR_SOLICITACAO - sol.imagens.count()
    if restante <= 0:
        return JsonResponse(
            {"success": False, "error": f"Limite de {MAX_FOTOS_POR_SOLICITACAO} fotos por evidência."}, status=400
        )

    criadas, erros = [], []
    for arq in arquivos[:restante]:
        try:
            jpeg = _processar_foto(arq)
        except ValueError as e:
            erros.append(str(e))
            continue
        nome = re.sub(r"\.[^.]+$", "", arq.name or "foto")[:200] + ".jpg"
        criadas.append(ImagemSolicitacaoLivre.objects.create(
            solicitacao=sol, nome_arquivo=nome, legenda=legenda,
            arquivo_base64=base64.b64encode(jpeg).decode("ascii"),
        ))
    if len(arquivos) > restante:
        erros.append(f"Apenas {restante} foto(s) cabiam no limite de {MAX_FOTOS_POR_SOLICITACAO} por evidência.")
    if not criadas:
        return JsonResponse({"success": False, "error": " ".join(erros)}, status=400)
    return JsonResponse({"success": True, "imagens": [_serialize_imagem(i) for i in criadas], "avisos": erros})


@login_required
@require_POST
def api_livre_imagem_delete(request, pk):
    get_object_or_404(ImagemSolicitacaoLivre, pk=pk).delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def api_livre_imagem_legenda(request, pk):
    img = get_object_or_404(ImagemSolicitacaoLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    img.legenda = str(data.get("legenda") or "").strip()[:255]
    img.save(update_fields=["legenda"])
    return JsonResponse({"success": True})


@login_required
def livre_imagem_arquivo(request, pk):
    import base64
    from django.http import Http404

    img = get_object_or_404(ImagemSolicitacaoLivre, pk=pk)
    try:
        conteudo = base64.b64decode(img.arquivo_base64 or "")
    except Exception:
        conteudo = b""
    if not conteudo:
        raise Http404("Arquivo não encontrado.")
    resp = HttpResponse(conteudo, content_type="image/jpeg")
    resp["Cache-Control"] = "private, max-age=31536000, immutable"  # o conteúdo de um id não muda
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


# -------------------------------------------------------------------- Word

@login_required
def livre_export_docx(request, pk):
    from .services.relatorio_livre_docx import gerar_relatorio_livre_docx

    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    solicitacoes = list(aud.solicitacoes.prefetch_related("imagens"))
    buf = gerar_relatorio_livre_docx(aud, solicitacoes)
    nome = re.sub(r"[^a-zA-Z0-9_-]+", "_", aud.titulo).strip("_")[:60] or "auditoria"
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    resp["Content-Disposition"] = f'attachment; filename="Relatorio_Auditoria_Livre_{nome}_{aud.pk}.docx"'
    return resp
