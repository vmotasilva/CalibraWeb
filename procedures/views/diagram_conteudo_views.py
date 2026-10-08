# -*- coding: utf-8 -*-
"""APIs do conteúdo dos blocos: imagens, sincronização com o RH, busca de procedimentos/diagramas e abertura de diagramas."""

import io
import json

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from PIL import Image, ImageOps

from ..models_diagram import Diagrama, ImagemDiagrama, StatusDiagrama

PERM_EDITAR = 'core.nav_diagramas_editor'
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
LADO_MAXIMO = 320
TIPOS_ACEITOS = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp', 'GIF': 'image/gif'}


def _pode_editar(user) -> bool:
    return bool(user.is_superuser or user.has_perm(PERM_EDITAR))


def _nao_autenticado():
    return JsonResponse({"error": "Autenticação necessária."}, status=401)


@require_http_methods(["POST"])
def api_imagem_upload(request):
    """Recebe uma imagem, valida, reduz (máx. 320 px) e guarda. Retorna o id para usar no bloco."""
    if not request.user.is_authenticated:
        return _nao_autenticado()
    if not _pode_editar(request.user):
        return JsonResponse({"error": "Você não tem permissão para enviar imagens."}, status=403)

    arquivo = request.FILES.get('arquivo')
    if arquivo is None:
        return JsonResponse({"error": "Envie o arquivo no campo 'arquivo'."}, status=400)
    if arquivo.size > MAX_UPLOAD_BYTES:
        return JsonResponse({"error": "Imagem grande demais (máximo de 2 MB)."}, status=400)

    try:
        imagem = Image.open(arquivo)
        formato = imagem.format
        if formato not in TIPOS_ACEITOS:
            return JsonResponse({"error": "Formato não suportado. Use JPG, PNG, WEBP ou GIF."}, status=400)
        imagem = ImageOps.exif_transpose(imagem)
        imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
        tem_transparencia = imagem.mode in ('RGBA', 'LA') or (imagem.mode == 'P' and 'transparency' in imagem.info)
        saida = io.BytesIO()
        if tem_transparencia:
            imagem.convert('RGBA').save(saida, format='PNG', optimize=True)
            content_type = 'image/png'
        else:
            imagem.convert('RGB').save(saida, format='JPEG', quality=85, optimize=True)
            content_type = 'image/jpeg'
    except Exception:
        return JsonResponse({"error": "Arquivo de imagem inválido."}, status=400)

    registro = ImagemDiagrama.objects.create(
        nome=(arquivo.name or '')[:120], content_type=content_type, dados=saida.getvalue(),
        tamanho=len(saida.getvalue()), criado_por=request.user,
    )
    return JsonResponse({"id": registro.id, "tamanho": registro.tamanho}, status=201)


@require_http_methods(["GET"])
def api_imagem_servir(request, imagem_id):
    if not request.user.is_authenticated:
        return _nao_autenticado()
    registro = ImagemDiagrama.objects.filter(pk=imagem_id).first()
    if registro is None:
        return HttpResponse(status=404)
    resposta = HttpResponse(bytes(registro.dados), content_type=registro.content_type)
    resposta['Cache-Control'] = 'private, max-age=86400, immutable'  # o conteúdo de um id nunca muda
    return resposta


@require_http_methods(["POST"])
def api_colaboradores_sincronizar(request):
    """Dados atuais do RH para uma lista de colaboradores (para o "Atualizar do RH")."""
    if not request.user.is_authenticated:
        return _nao_autenticado()
    try:
        ids = json.loads(request.body).get('ids', [])
    except Exception:
        return JsonResponse({"error": "JSON inválido."}, status=400)
    if (not isinstance(ids, list) or len(ids) > 300
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)):
        return JsonResponse({"error": "Informe até 300 ids de colaboradores."}, status=400)

    from rh.models import Colaborador
    encontrados = {
        c.id: {"existe": True, "nome": c.nome_completo, "cargo": c.cargo or '', "setor_id": c.setor_id, "tem_foto": bool(c.foto)}
        for c in Colaborador.objects.filter(pk__in=ids).select_related('setor')
    }
    resultado = {str(i): encontrados.get(i, {"existe": False}) for i in ids}
    return JsonResponse({"results": resultado})


@require_http_methods(["GET"])
def api_procedimentos_buscar(request):
    if not request.user.is_authenticated:
        return _nao_autenticado()
    termo = request.GET.get('q', '').strip()
    if len(termo) < 2:
        return JsonResponse({"results": []})
    from ..models import Procedimento
    qs = Procedimento.objects.filter(models.Q(codigo__icontains=termo) | models.Q(nome__icontains=termo)).order_by('codigo')[:10]
    return JsonResponse({"results": [{"id": p.id, "codigo": p.codigo or '', "nome": p.nome or ''} for p in qs]})


@require_http_methods(["GET"])
def api_diagramas_buscar(request):
    if not request.user.is_authenticated:
        return _nao_autenticado()
    termo = request.GET.get('q', '').strip()
    if len(termo) < 1:
        return JsonResponse({"results": []})
    filtro = models.Q(titulo__icontains=termo) | models.Q(codigo__icontains=termo)
    if termo.lstrip('#').isdigit():
        filtro |= models.Q(numero=int(termo.lstrip('#')))
    qs = Diagrama.objects.filter(ativo=True).filter(filtro).order_by('numero')[:10]
    return JsonResponse({"results": [{"id": str(d.id), "identificador": d.identificador, "titulo": d.titulo} for d in qs]})


@login_required
def diagrama_abrir_view(request, diagrama_id):
    """Abre o diagrama na revisão vigente (aprovada) ou, sem ela, na última revisão."""
    diagrama = get_object_or_404(Diagrama, id=diagrama_id)
    versao = (diagrama.versoes.filter(status=StatusDiagrama.APROVADO).order_by('-revisao').first()
              or diagrama.versoes.order_by('-revisao').first())
    if versao is None:
        return redirect('procedures:diagramas_lista')
    return redirect('procedures:diagrama_editor', versao_id=versao.id)
