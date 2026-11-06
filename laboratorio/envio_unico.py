"""Token de envio único para os formulários de lançamento (HC e CF): impede gravar o mesmo envio mais de uma vez.

O formulário recebe um token aleatório ao ser exibido. No POST, o token é gravado numa tabela com `unique` na mesma
transação que salva o registro: um segundo envio com o mesmo token (clique duplo, duas abas, reenvio de rede) viola a
unicidade e é descartado. Se o salvamento falhar, a transação desfaz o token e o formulário pode ser reenviado.
O token é obrigatório: um POST sem ele (página aberta antes desta proteção) não grava nada e o formulário é reexibido com os dados e um token novo.
"""
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import EnvioUnico

TAMANHO_MAX = 64
RETENCAO = timedelta(days=2)


class EnvioDuplicado(Exception):
    """O token deste envio já foi usado: o lançamento já foi registrado."""


class EnvioSemToken(Exception):
    """O POST não trouxe o token (página de formulário antiga, aberta antes desta proteção)."""


def novo_token():
    return secrets.token_urlsafe(24)


def token_do_formulario(request):
    """Token a embutir no formulário: o já enviado (reexibição por erro de validação) ou um novo."""
    if request.method == "POST":
        enviado = (request.POST.get("envio_token") or "").strip()[:TAMANHO_MAX]
        if enviado:
            return enviado
    return novo_token()


def registrar(request):
    """Consome o token do POST. Levanta EnvioSemToken se ele não veio e EnvioDuplicado se já foi usado.

    Deve ser chamado dentro de `transaction.atomic()` junto com o salvamento do registro.
    """
    token = (request.POST.get("envio_token") or "").strip()[:TAMANHO_MAX]
    if not token:
        raise EnvioSemToken()
    try:
        with transaction.atomic():
            EnvioUnico.objects.create(token=token)
    except IntegrityError:
        raise EnvioDuplicado()
    EnvioUnico.objects.filter(criado_em__lt=timezone.now() - RETENCAO).delete()
