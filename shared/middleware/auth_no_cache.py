# -*- coding: utf-8 -*-
"""
Evita cache do navegador em telas sensíveis de autenticação/2FA.
"""


class AuthNoCacheMiddleware:
    """Aplica cabeçalhos anti-cache a páginas de autenticação para evitar CSRF com formulários stale."""

    AUTH_PATH_PREFIXES = (
        "/account/login/",
        "/account/two_factor/",
        "/account/logout/",
        "/logout/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if any(request.path.startswith(prefix) for prefix in self.AUTH_PATH_PREFIXES):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            response["Vary"] = ", ".join(
                part for part in [response.get("Vary", ""), "Cookie"] if part
            )

        return response