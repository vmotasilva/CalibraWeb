"""Modo Apresentação ("telão"): player em tela cheia + gestão dos modelos de apresentação personalizados."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from shared.models import ModeloApresentacao

from . import providers


@login_required
@never_cache
def telao_view(request):
    definicao = providers.obter_playlist(request.user, (request.GET.get("p") or "").strip())
    try:
        duracao = min(max(int(request.GET.get("t") or 0), 5), 120)
    except ValueError:
        duracao = 0
    return render(request, "shared/telao.html", {
        "playlist": definicao["chave"],
        "playlist_nome": definicao["nome"],
        "playlists": playlists_para_menu(request.user),
        "api_url": reverse("telao_api"),
        "duracao": duracao,
        "resumo": request.GET.get("resumo") == "1" or definicao["resumo"],
    })


@login_required
@never_cache
def telao_api(request):
    chave = (request.GET.get("p") or "").strip()
    slides = providers.montar_playlist(request.user, chave, resumo=request.GET.get("resumo") == "1", fresco=True)
    return JsonResponse({"slides": slides, "gerado_em": timezone.localtime().strftime("%H:%M:%S")})


def playlists_para_menu(user):
    """[(chave, nome, ícone, personalizada)] — padrões primeiro, depois os modelos criados pelos usuários."""
    padroes = [(k, v[0], v[1], False) for k, v in providers.PLAYLISTS.items()]
    personalizadas = [(m.chave, m.nome, m.icone or "bi-display", True) for m in providers.modelos_visiveis(user)]
    return padroes + personalizadas


# ---------------------------------------------------------------------------
# Gestão dos modelos
# ---------------------------------------------------------------------------
def _itens_do_post(post, user) -> list[dict]:
    itens = []
    for chave in post.getlist("prov"):
        if chave not in providers.PROVEDORES or any(i["provedor"] == chave for i in itens):
            continue
        bruto = (post.get(f"dur_{chave}") or "").strip()
        filtros = providers.limpar_filtros(chave, post.getlist, post.get, user)
        itens.append({"provedor": chave, "duracao": min(max(int(bruto), 5), 120) if bruto.isdigit() else None,
                      "filtros": filtros})
    return itens


def _ler_modelo(request, modelo):
    """Aplica o formulário ao modelo; devolve lista de erros (vazia = pode salvar)."""
    p = request.POST
    modelo.nome = (p.get("nome") or "").strip()[:100]
    modelo.descricao = (p.get("descricao") or "").strip()[:200]
    icone = (p.get("icone") or "").strip()
    modelo.icone = icone if icone.startswith("bi-") and len(icone) <= 40 else "bi-display"
    bruto = (p.get("duracao_padrao") or "").strip()
    modelo.duracao_padrao = min(max(int(bruto), 5), 120) if bruto.isdigit() else 15
    modelo.resumo = p.get("resumo") == "on"
    modelo.compartilhada = p.get("compartilhada") == "on"
    modelo.ativo = p.get("ativo", "on") == "on"
    modelo.itens = _itens_do_post(p, request.user)
    erros = []
    if not modelo.nome:
        erros.append("Informe o nome da apresentação.")
    if not modelo.itens:
        erros.append("Escolha ao menos um conteúdo.")
    return erros


@login_required
def modelos_lista(request):
    modelos = list(providers.modelos_visiveis(request.user).select_related("criado_por"))
    for m in modelos:
        m.pode_editar = m.editavel_por(request.user)
        m.rotulos = [providers.ROTULOS_PROVEDORES[i["provedor"]][0] for i in m.itens
                     if isinstance(i, dict) and i.get("provedor") in providers.ROTULOS_PROVEDORES]
    return render(request, "shared/telao_modelos.html", {
        "modelos": modelos,
        "padroes": [(k, v[0], v[1], [providers.ROTULOS_PROVEDORES[p][0] for p in v[2]]) for k, v in providers.PLAYLISTS.items()],
    })


@login_required
def modelo_form(request, pk=None):
    if pk:
        modelo = get_object_or_404(ModeloApresentacao, pk=pk)
        if not modelo.editavel_por(request.user):
            return HttpResponseForbidden("Apenas quem criou a apresentação (ou um administrador) pode editá-la.")
    else:
        modelo = ModeloApresentacao(criado_por=request.user)
        base = (request.GET.get("base") or "").strip()  # copia um modelo padrão ou outro personalizado
        if base in providers.PLAYLISTS:
            nome, icone, provs = providers.PLAYLISTS[base]
            modelo.nome, modelo.icone = f"{nome} (cópia)", icone
            modelo.itens = [{"provedor": p, "duracao": None} for p in provs]
        elif base[:1] == "m" and base[1:].isdigit():
            origem = providers.modelos_visiveis(request.user).filter(pk=int(base[1:])).first()
            if origem:
                modelo.nome, modelo.icone, modelo.descricao = f"{origem.nome} (cópia)", origem.icone, origem.descricao
                modelo.itens, modelo.duracao_padrao, modelo.resumo = list(origem.itens), origem.duracao_padrao, origem.resumo

    erros = []
    if request.method == "POST":
        erros = _ler_modelo(request, modelo)
        if not erros:
            modelo.save()
            messages.success(request, f"Apresentação “{modelo.nome}” salva.")
            return redirect("telao_modelos")
        for e in erros:
            messages.error(request, e)

    escolhidos = {i["provedor"]: i for i in (modelo.itens or []) if isinstance(i, dict)}
    # escolhidos primeiro (na ordem salva), depois os demais conteúdos disponíveis
    ordem = [k for k in escolhidos if k in providers.ROTULOS_PROVEDORES] + [
        k for k in providers.ROTULOS_PROVEDORES if k not in escolhidos]
    linhas = []
    for k in ordem:
        atual = (escolhidos.get(k) or {}).get("filtros") or {}
        campos = providers.campos_filtro(k, request.user)
        for c in campos:
            val = atual.get(c["nome"])
            c["sel"] = {str(v) for v in val} if c["tipo"] == "multi" and val else set()
            c["val"] = val if c["tipo"] != "multi" else None
            c["campo"] = f"f_{k}_{c['nome']}"
        linhas.append({"chave": k, "rotulo": providers.ROTULOS_PROVEDORES[k][0], "icone": providers.ROTULOS_PROVEDORES[k][1],
                       "ativo": k in escolhidos, "duracao": (escolhidos.get(k) or {}).get("duracao") or "",
                       "campos": campos, "n_filtros": len(atual)})
    return render(request, "shared/telao_modelo_form.html", {"modelo": modelo, "linhas": linhas, "novo": not modelo.pk})


@login_required
@require_POST
def modelo_excluir(request, pk):
    modelo = get_object_or_404(ModeloApresentacao, pk=pk)
    if not modelo.editavel_por(request.user):
        return HttpResponseForbidden("Apenas quem criou a apresentação (ou um administrador) pode excluí-la.")
    nome = modelo.nome
    modelo.delete()
    messages.success(request, f"Apresentação “{nome}” excluída.")
    return redirect("telao_modelos")
