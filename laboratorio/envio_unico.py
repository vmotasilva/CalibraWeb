"""Token de envio único para os formulários de lançamento (HC e CF): impede gravar o mesmo envio mais de uma vez.

O formulário recebe um token aleatório ao ser exibido. No POST, o token é gravado numa tabela com `unique` na mesma
transação que salva o registro: um segundo envio com o mesmo token (clique duplo, duas abas, reenvio de rede) viola a
unicidade e é descartado. Se o salvamento falhar, a transação desfaz o token e o formulário pode ser reenviado.
"""
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import EnvioUnico

TAMANHO_MAX = 64
RETENCAO = timedelta(days=2)


class EnvioDuplicado(Exception):
    pass


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
    """Consome o token do POST. Levanta EnvioDuplicado se ele já foi usado. Sem token (clientes antigos), não restringe.

    Deve ser chamado dentro de `transaction.atomic()` junto com o salvamento do registro.
    """
    token = (request.POST.get("envio_token") or "").strip()[:TAMANHO_MAX]
    if not token:
        return
    try:
        with transaction.atomic():
            EnvioUnico.objects.create(token=token)
    except IntegrityError:
        raise EnvioDuplicado()
    EnvioUnico.objects.filter(criado_em__lt=timezone.now() - RETENCAO).delete()
