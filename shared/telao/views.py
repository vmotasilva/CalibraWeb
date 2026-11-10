"""Modo Apresentação ("telão"): player em tela cheia que roda em loop os slides de cada módulo."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from . import providers


def _playlist(request):
    p = (request.GET.get("p") or "").strip()
    return p if p in providers.PLAYLISTS else providers.PLAYLIST_PADRAO


@login_required
@never_cache
def telao_view(request):
    playlist = _playlist(request)
    try:
        duracao = min(max(int(request.GET.get("t") or 0), 5), 120)
    except ValueError:
        duracao = 0
    return render(request, "shared/telao.html", {
        "playlist": playlist,
        "playlist_nome": providers.PLAYLISTS[playlist][0],
        "playlists": [(k, v[0], v[1]) for k, v in providers.PLAYLISTS.items()],
        "api_url": reverse("telao_api"),
        "duracao": duracao,
        "resumo": request.GET.get("resumo") == "1",
    })


@login_required
@never_cache
def telao_api(request):
    slides = providers.montar_playlist(request.user, _playlist(request), resumo=request.GET.get("resumo") == "1")
    return JsonResponse({"slides": slides})
