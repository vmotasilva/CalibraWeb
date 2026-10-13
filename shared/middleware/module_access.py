# -*- coding: utf-8 -*-
"""
Middleware de controle de acesso por módulo e função.

Aplica no servidor as permissões `core.nav_*` configuradas em
`/rh/usuarios/<id>/`, usando o mapa `VIEW_NAME_TO_PERMISSION`
(`shared/permissions.py`). Para uma view mapeada, exige:
  1. o módulo ("No menu", `nav_mod_*`) ou o grupo legado do módulo; e
  2. a permissão da função ("Acessar").

Modo de operação (setting/variável de ambiente PERMISSIONS_ENFORCEMENT):
  - "log" (padrão): só registra no logger `shared.access` o que seria bloqueado.
  - "enforce": bloqueia (403 em requisições AJAX/API, redirect com mensagem nas demais).
  - "off": desligado.

Views não mapeadas em NAV_STRUCTURE continuam liberadas (dependem de login).
Superusuários e staff passam sempre.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from shared.permissions import (
    VIEW_NAME_TO_PERMISSION,
    _nav_module_config,
    has_module_access,
    has_view_access,
)

logger = logging.getLogger("shared.access")


class ModuleAccessMiddleware:
    # Prefixos que nunca passam pela checagem
    EXEMPT_PREFIXES = (
        "/static/",
        "/media/",
        "/admin/",
        "/accounts/",
        "/login/",
        "/logout/",
        "/acesso-negado/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    @staticmethod
    def _mode():
        mode = str(getattr(settings, "PERMISSIONS_ENFORCEMENT", "log")).lower()
        return mode if mode in {"off", "log", "enforce"} else "log"

    @staticmethod
    def _wants_json(request):
        return (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("accept", "")
            or request.content_type == "application/json"
            or "/api/" in request.path
        )

    @staticmethod
    def _denial_reason(user, view_name):
        """Retorna None se liberado, ou o motivo do bloqueio."""
        data = VIEW_NAME_TO_PERMISSION.get(view_name)
        if not data:
            return None  # view não mapeada: sem controle por função

        module_key = data.get("module")
        module = _nav_module_config(module_key) if module_key else None
        if module and module.get("module_perm") and not has_module_access(user, module_key):
            return f"sem acesso ao módulo '{module_key}'"

        if not has_view_access(user, view_name):
            return f"sem a permissão '{data.get('perm')}'"
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None  # @login_required cuida disso
        if user.is_superuser or user.is_staff:
            return None
        if request.path.startswith(self.EXEMPT_PREFIXES):
            return None

        mode = self._mode()
        if mode == "off":
            return None

        match = getattr(request, "resolver_match", None)
        view_name = getattr(match, "view_name", None)
        if not view_name:
            return None

        try:
            reason = self._denial_reason(user, view_name)
        except Exception:
            logger.exception("Falha ao checar permissão de %s", view_name)
            return None
        if not reason:
            return None

        logger.warning(
            "ACESSO %s: user=%s view=%s path=%s motivo=%s",
            "BLOQUEADO" if mode == "enforce" else "SERIA BLOQUEADO",
            user.username, view_name, request.path, reason,
        )
        if mode != "enforce":
            return None

        if self._wants_json(request):
            return JsonResponse(
                {"success": False, "error": "Você não tem permissão para acessar este recurso."},
                status=403,
            )
        messages.error(request, "Você não tem permissão para acessar esta página.")
        return redirect("/")
