"""Central de Ocorrências: tela única para listar e tratar ocorrências de todos os módulos."""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from shared import ocorrencias as central

ABAS = (("minhas", "Envolvem você"), ("abertas", "Todas em aberto"), ("encerradas", "Encerradas"))


def _lista_para(request):
    aba = (request.GET.get("aba") or "").strip()
    origem = (request.GET.get("origem") or "").strip()
    q = (request.GET.get("q") or "").strip().lower()
    atraso = request.GET.get("atraso") == "1"
    if aba not in {a for a, _ in ABAS}:
        aba = ""
    if origem not in central.ORIGENS:
        origem = ""

    abertas = central.listar_ocorrencias(request.user, "abertas", origem)
    encerradas = None
    if aba == "encerradas":
        encerradas = central.listar_ocorrencias(request.user, "encerradas", origem)

    minhas = [i for i in abertas if i.envolve_usuario]
    # Sem aba escolhida: prioriza o que envolve o usuário; se não há nada, mostra todas.
    if not aba:
        aba = "minhas" if minhas else "abertas"
    itens = {"minhas": minhas, "abertas": abertas, "encerradas": encerradas or []}[aba]
    if aba == "encerradas":
        atraso = False
    elif atraso:
        itens = [i for i in itens if i.vencida]
    if q:
        itens = [
            i for i in itens
            if q in f"{i.titulo} {i.descricao} {i.origem_nome} {' '.join(i.responsaveis)}".lower()
        ]
    por_origem = {}
    for i in abertas:
        por_origem[i.origem] = por_origem.get(i.origem, 0) + 1
    return {
        "itens": itens,
        "aba": aba,
        "abas": [
            (a, nome, len(minhas) if a == "minhas" else len(abertas) if a == "abertas" else None)
            for a, nome in ABAS
        ],
        "origem": origem,
        "origens": [(k, o.nome, o.icon, por_origem.get(k, 0)) for k, o in central.ORIGENS.items()],
        "q": q,
        "atraso": atraso,
        "total_vencidas": sum(1 for i in abertas if i.vencida),
    }


@login_required
def ocorrencias_central_view(request):
    ctx = _lista_para(request)
    abrir = (request.GET.get("abrir") or "").strip()
    ctx["abrir"] = abrir if any(i.uid == abrir for i in ctx["itens"]) else ""
    ctx["next_qs"] = request.GET.urlencode()
    return render(request, "shared/ocorrencias_central.html", ctx)


@login_required
@require_POST
def ocorrencias_acao_view(request):
    res = central.executar_acao(
        request.user,
        request.POST.get("uid", ""),
        request.POST.get("acao", ""),
        {
            "texto": request.POST.get("texto", ""),
            "destinatarios": request.POST.getlist("destinatarios"),
            "responsaveis": request.POST.getlist("responsaveis"),
            "responsavel": request.POST.get("responsavel", "") or next(iter(request.POST.getlist("responsaveis")), ""),
            "prazo": request.POST.get("prazo", ""),
            "acao_id": request.POST.get("acao_id", ""),
        },
    )
    (messages.success if res.ok else messages.error)(request, res.msg)
    qs = (request.POST.get("next_qs") or "").strip()
    # next_qs vem do próprio formulário; mantém apenas parâmetros conhecidos da listagem
    from urllib.parse import parse_qsl

    permitido = {"aba", "origem", "q", "atraso"}
    params = [(k, v) for k, v in parse_qsl(qs) if k in permitido]
    if res.ok or request.POST.get("uid"):
        params.append(("abrir", request.POST.get("uid", "")))  # reabre o pop-up da ocorrência tratada
    qs = urlencode(params)
    url = reverse("ocorrencias_central") + (f"?{qs}" if qs else "")
    return redirect(url)


@login_required
def api_usuarios_view(request):
    """Busca (AJAX) de usuários para escolher responsáveis: ?q=texto (nome, colaborador ou login)."""
    return JsonResponse({"results": central.buscar_usuarios(request.GET.get("q", ""), so_usuarios=request.GET.get("modo") == "usuario")})


@login_required
def api_plano_view(request, origem, pk):
    """Plano de ação da ocorrência (usado pelo widget das telas de origem)."""
    dados = central.plano_json(request.user, origem, pk)
    if dados is None:
        return JsonResponse({"erro": "Ocorrência não encontrada ou sem acesso."}, status=404)
    return JsonResponse(dados)


@login_required
@require_POST
def api_plano_acao_view(request):
    """Executa uma ação do plano (nova, concluir, redirecionar, cancelar) e devolve o plano atualizado."""
    uid = request.POST.get("uid", "")
    acao = request.POST.get("acao", "")
    if acao not in central.ACOES_PLANO:
        return JsonResponse({"ok": False, "erro": "Ação inválida."}, status=400)
    res = central.executar_acao(request.user, uid, acao, {
        "texto": request.POST.get("texto", ""),
        "responsaveis": request.POST.getlist("responsaveis"),
        "prazo": request.POST.get("prazo", ""),
        "acao_id": request.POST.get("acao_id", ""),
    })
    origem, _, pk = uid.partition(":")
    plano = central.plano_json(request.user, origem, int(pk)) if pk.isdigit() else None
    return JsonResponse({"ok": res.ok, "mensagem": res.msg, "erro": "" if res.ok else res.msg, "plano": plano},
                        status=200 if res.ok else 400)
