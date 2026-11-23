"""Plano de Ação (CAPA) da Auditoria Livre.

Fluxo: o auditor classifica uma evidência como NC (ou OM) -> o auditado, por link público sem
login, informa causa raiz, ação, responsável, prazo e anexos -> o auditor aprova ou rejeita.
"""
import base64
import mimetypes
import os
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from .models import (
    AuditoriaLivre,
    CapaLinkLivre,
    EvidenciaPlanoAcaoLivre,
    ImagemSolicitacaoLivre,
    SolicitacaoLivre,
)
from .views_livre import _json_body

# --- limites e validação dos anexos (o portal aceita upload sem login, então é restritivo)
EXTENSOES_PERMITIDAS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx",
    ".xls", ".xlsx", ".csv", ".txt",
}
MIMES_EXIBICAO_SEGURA = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}
MAX_BYTES_ANEXO = 10 * 1024 * 1024
MAX_ANEXOS_POR_ITEM = 10
EDITAVEIS = ("PENDENTE", "REJEITADO")  # estados em que o plano pode ser preenchido/alterado


def _sem_base64(qs_model):
    return qs_model.objects.defer("arquivo_base64")


def _numeros(aud):
    """Numeração das evidências (#1, #2…), igual à do Excel e do Word: posição na auditoria."""
    ids = aud.solicitacoes.order_by("ordem", "id").values_list("id", flat=True)
    return {sid: n for n, sid in enumerate(ids, start=1)}


def _itens_capa(solicitacoes_qs, numeros, token=None):
    """Serializa as evidências com desvio (e seus anexos) para o painel ou o portal."""
    qs = solicitacoes_qs.prefetch_related(
        Prefetch("imagens", queryset=_sem_base64(ImagemSolicitacaoLivre)),
        Prefetch("evidencias_capa", queryset=_sem_base64(EvidenciaPlanoAcaoLivre)),
    ).order_by("ordem", "id")
    itens = []
    for s in qs:
        if token:
            url_img = lambda i: reverse("auditoria:livre_capa_imagem_publico", args=[token, i.pk])
            url_ev = lambda e: reverse("auditoria:livre_capa_anexo_publico", args=[token, e.pk])
        else:
            url_img = lambda i: i.url
            url_ev = lambda e: reverse("auditoria:livre_capa_anexo", args=[e.pk])
        itens.append({
            "id": s.id,
            "numero": numeros.get(s.id, 0),
            "topico": s.topico,
            "solicitacao": s.solicitacao,
            "evidencia": s.evidencia,
            "observacao": s.observacao,
            "conclusao": s.conclusao,
            "conclusao_display": s.get_conclusao_display(),
            "grau_nc": s.get_grau_nc_display() if s.grau_nc else "",
            "capa_status": s.capa_status,
            "capa_status_display": s.get_capa_status_display(),
            "editavel": s.capa_status in EDITAVEIS,
            "causa_raiz": s.capa_causa_raiz,
            "acao_corretiva": s.capa_acao_corretiva,
            "responsavel": s.capa_responsavel,
            "prazo": s.capa_prazo.isoformat() if s.capa_prazo else "",
            "respondido_em": s.capa_respondido_em,
            "respondido_por": s.capa_respondido_por_nome,
            "parecer": s.capa_parecer_auditor,
            "fotos": [{"url": url_img(i), "legenda": i.legenda} for i in s.imagens.all()],
            "anexos": [{"id": e.id, "url": url_ev(e), "nome": e.nome_arquivo} for e in s.evidencias_capa.all()],
        })
    return itens


def _contagem(itens):
    c = {k: 0 for k in ("PENDENTE", "AGUARDANDO_REVISAO", "APROVADO", "REJEITADO")}
    for i in itens:
        c[i["capa_status"]] += 1
    c["total"] = len(itens)
    return c


def _aplicar_plano(sol, dados, enviar, respondente=""):
    """Grava os campos do plano. Retorna mensagem de erro ou None. Usado pelo portal e pelo auditor."""
    if sol.capa_status not in EDITAVEIS:
        return "Este plano está em revisão ou já foi aprovado e não pode ser alterado."
    prazo_txt = str(dados.get("prazo") or "").strip()
    prazo = None
    if prazo_txt:
        try:
            prazo = date.fromisoformat(prazo_txt)
        except ValueError:
            return "Prazo inválido."
    sol.capa_causa_raiz = str(dados.get("causa_raiz") or "").strip()
    sol.capa_acao_corretiva = str(dados.get("acao_corretiva") or "").strip()
    sol.capa_responsavel = str(dados.get("responsavel") or "").strip()[:255]
    sol.capa_prazo = prazo
    if respondente:
        sol.capa_respondido_por_nome = respondente[:255]
    if enviar:
        if not (sol.capa_causa_raiz and sol.capa_acao_corretiva and sol.capa_responsavel and sol.capa_prazo):
            return "Para enviar o plano, preencha causa raiz, ação, responsável e prazo."
        sol.capa_status = "AGUARDANDO_REVISAO"
        sol.capa_respondido_em = timezone.now()
    elif sol.capa_status == "REJEITADO":
        sol.capa_status = "PENDENTE"  # rascunho após rejeição volta a pendente (parecer fica visível)
    sol.save()
    return None


def _salvar_anexos(sol, arquivos):
    """Valida e grava anexos. Retorna (criados, erros)."""
    criados, erros = [], []
    vagas = MAX_ANEXOS_POR_ITEM - sol.evidencias_capa.count()
    for f in arquivos:
        if vagas <= 0:
            erros.append(f"Limite de {MAX_ANEXOS_POR_ITEM} anexos por item atingido.")
            break
        nome = os.path.basename(f.name or "arquivo")[:255]
        ext = os.path.splitext(nome)[1].lower()
        if ext not in EXTENSOES_PERMITIDAS:
            erros.append(f"'{nome}': tipo de arquivo não permitido.")
            continue
        if f.size > MAX_BYTES_ANEXO:
            erros.append(f"'{nome}' excede 10 MB.")
            continue
        mime = mimetypes.guess_type(nome)[0] or "application/octet-stream"
        criados.append(EvidenciaPlanoAcaoLivre.objects.create(
            solicitacao=sol, nome_arquivo=nome, tipo_arquivo=mime,
            arquivo_base64=base64.b64encode(f.read()).decode("ascii"),
        ))
        vagas -= 1
    return criados, erros


def _responder_anexo(obj, nome, mime):
    try:
        conteudo = base64.b64decode(obj.arquivo_base64 or "")
    except Exception:
        conteudo = b""
    if not conteudo:
        raise Http404("Arquivo não encontrado.")
    exibir = mime in MIMES_EXIBICAO_SEGURA
    resp = HttpResponse(conteudo, content_type=mime if exibir else "application/octet-stream")
    resp["Content-Disposition"] = content_disposition_header(not exibir, nome or f"arquivo-{obj.pk}")
    resp["Cache-Control"] = "private, max-age=31536000, immutable"
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


# ====================================================================== auditor

@login_required
def livre_capa(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    desvios = aud.solicitacoes.filter(conclusao__in=("NC", "OM"))
    itens = _itens_capa(desvios, _numeros(aud))
    links = []
    for l in aud.links_capa.all():
        links.append({
            "id": l.id, "topico": l.topico, "incluir_om": l.incluir_om, "ativo": l.ativo,
            "expirado": l.is_expired, "expira_em": l.expira_em, "ultimo_acesso_em": l.ultimo_acesso_em,
            "url": request.build_absolute_uri(reverse("auditoria:livre_capa_portal", args=[l.token])),
        })
    topicos = sorted({t for t in aud.solicitacoes.values_list("topico", flat=True) if t}, key=str.casefold)
    return render(request, "auditoria/livre_capa.html", {
        "aud": aud, "itens": itens, "resumo": _contagem(itens), "links": links, "topicos": topicos,
    })


@login_required
@require_POST
def api_livre_capa_gerar_link(request, pk):
    aud = get_object_or_404(AuditoriaLivre, pk=pk)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    try:
        dias = int(data.get("dias_validade") or 15)
    except (TypeError, ValueError):
        dias = 15
    dias = max(1, min(dias, 90))
    link = CapaLinkLivre.objects.create(
        auditoria=aud, dias_validade=dias, incluir_om=bool(data.get("incluir_om")),
        topico=str(data.get("topico") or "").strip()[:255], criado_por=request.user,
        expira_em=timezone.now() + timezone.timedelta(days=dias),
    )
    return JsonResponse({
        "success": True,
        "url": request.build_absolute_uri(reverse("auditoria:livre_capa_portal", args=[link.token])),
    })


@login_required
@require_POST
def api_livre_capa_revogar_link(request, pk):
    link = get_object_or_404(CapaLinkLivre, pk=pk)
    link.ativo = False
    link.save(update_fields=["ativo"])
    return JsonResponse({"success": True})


@login_required
@require_POST
def api_livre_capa_salvar(request, pk):
    """O auditor registra/ajusta o plano diretamente (ex.: definido em reunião)."""
    sol = get_object_or_404(SolicitacaoLivre, pk=pk, conclusao__in=("NC", "OM"))
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    nome = request.user.get_full_name() or request.user.get_username()
    erro = _aplicar_plano(sol, data, bool(data.get("enviar")), respondente=nome)
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    return JsonResponse({"success": True, "status": sol.capa_status})


@login_required
@require_POST
def api_livre_capa_revisar(request, pk):
    sol = get_object_or_404(SolicitacaoLivre, pk=pk, conclusao__in=("NC", "OM"))
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Requisição inválida."}, status=400)
    decisao = data.get("status")
    parecer = str(data.get("parecer") or "").strip()
    if decisao not in ("APROVADO", "REJEITADO"):
        return JsonResponse({"success": False, "error": "Decisão inválida."}, status=400)
    if sol.capa_status == "PENDENTE":
        return JsonResponse({"success": False, "error": "Ainda não há plano enviado para revisar."}, status=400)
    if decisao == "REJEITADO" and not parecer:
        return JsonResponse({"success": False, "error": "Informe o motivo da rejeição no parecer."}, status=400)
    sol.capa_status = decisao
    sol.capa_parecer_auditor = parecer
    sol.save()
    return JsonResponse({"success": True, "status": sol.capa_status, "status_display": sol.get_capa_status_display()})


@login_required
def livre_capa_anexo(request, pk):
    ev = get_object_or_404(EvidenciaPlanoAcaoLivre, pk=pk)
    return _responder_anexo(ev, ev.nome_arquivo, ev.tipo_arquivo)


# ======================================================================= público
# Sem login: tudo é validado pelo token do link (ativo, não expirado e dentro do escopo).

def _link_valido(token):
    link = CapaLinkLivre.objects.filter(token=token).select_related("auditoria").first()
    return link if link and link.is_valid else None


def livre_capa_portal(request, token):
    link = CapaLinkLivre.objects.filter(token=token).select_related("auditoria").first()
    if not link or not link.ativo:
        return render(request, "auditoria/livre_capa_portal.html", {
            "erro_titulo": "Link inválido ou desativado",
            "erro_msg": "Este link de plano de ação não é mais válido ou foi revogado pela coordenação.",
        }, status=404)
    if link.is_expired:
        return render(request, "auditoria/livre_capa_portal.html", {
            "erro_titulo": "Link expirado",
            "erro_msg": f"O acesso expirou em {link.expira_em:%d/%m/%Y}. Solicite um novo link ao auditor.",
        }, status=403)
    link.ultimo_acesso_em = timezone.now()
    link.save(update_fields=["ultimo_acesso_em"])
    itens = _itens_capa(link.solicitacoes(), _numeros(link.auditoria), token=token)
    resp = render(request, "auditoria/livre_capa_portal.html", {
        "link": link, "aud": link.auditoria, "itens": itens, "resumo": _contagem(itens), "token": token,
    })
    resp["Cache-Control"] = "no-store"
    resp["Referrer-Policy"] = "no-referrer"  # o token está na URL
    return resp


@require_POST
def api_livre_capa_responder_publico(request, token):
    link = _link_valido(token)
    if not link:
        return JsonResponse({"success": False, "error": "Link inválido ou expirado."}, status=403)
    sid = request.POST.get("solicitacao_id") or ""
    sol = get_object_or_404(link.solicitacoes(), pk=int(sid) if sid.isdigit() else 0)
    enviar = request.POST.get("enviar") == "true"
    erro = _aplicar_plano(sol, request.POST, enviar, respondente=(request.POST.get("respondente") or "").strip())
    if erro:
        return JsonResponse({"success": False, "error": erro}, status=400)
    criados, erros = _salvar_anexos(sol, request.FILES.getlist("anexos"))
    return JsonResponse({
        "success": True, "status": sol.capa_status, "avisos": erros,
        "anexos": [{"id": e.id, "nome": e.nome_arquivo,
                    "url": reverse("auditoria:livre_capa_anexo_publico", args=[token, e.pk])} for e in criados],
    })


@require_POST
def api_livre_capa_remover_anexo_publico(request, token, pk):
    link = _link_valido(token)
    if not link:
        return JsonResponse({"success": False, "error": "Link inválido ou expirado."}, status=403)
    ev = get_object_or_404(EvidenciaPlanoAcaoLivre, pk=pk, solicitacao__in=link.solicitacoes())
    if ev.solicitacao.capa_status not in EDITAVEIS:
        return JsonResponse({"success": False, "error": "O plano não pode mais ser alterado."}, status=400)
    ev.delete()
    return JsonResponse({"success": True})


def livre_capa_anexo_publico(request, token, pk):
    link = _link_valido(token)
    if not link:
        raise Http404("Arquivo não encontrado.")
    ev = get_object_or_404(EvidenciaPlanoAcaoLivre, pk=pk, solicitacao__in=link.solicitacoes())
    return _responder_anexo(ev, ev.nome_arquivo, ev.tipo_arquivo)


def livre_capa_imagem_publico(request, token, pk):
    link = _link_valido(token)
    if not link:
        raise Http404("Arquivo não encontrado.")
    img = get_object_or_404(ImagemSolicitacaoLivre, pk=pk, solicitacao__in=link.solicitacoes())
    return _responder_anexo(img, img.nome_arquivo, "image/jpeg")
