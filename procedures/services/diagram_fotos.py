# -*- coding: utf-8 -*-
"""Utilitário para as fotos de colaboradores (campo Base64 do RH) usadas nos blocos."""

import base64


def decodificar_foto_colaborador(valor):
    """Converte o campo foto (data URI ou Base64 puro) em (bytes, content_type). Retorna None se inválida."""
    if not valor:
        return None
    content_type = 'image/jpeg'
    if valor.startswith('data:'):
        cabecalho, _, valor = valor.partition(',')
        content_type = cabecalho[5:].split(';')[0] or content_type
    try:
        return base64.b64decode(valor, validate=False), content_type
    except Exception:
        return None
