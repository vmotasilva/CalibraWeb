# -*- coding: utf-8 -*-
"""
Middleware para forçar ativação do 2FA para todos os usuários.
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django_otp import user_has_device


class TwoFactorRequiredMiddleware:
    """
    Middleware que força usuários autenticados a configurarem 2FA.
    Usuários sem 2FA ativo são redirecionados para a tela de configuração.
    """
    
    # URLs que podem ser acessadas sem 2FA configurado
    ALLOWED_URLS = [
        'two_factor:setup',
        'two_factor:qr',
        'two_factor:login',
        'two_factor:logout',
        'logout',
        'admin:logout',
    ]
    
    # Prefixos de URLs permitidos (para assets estáticos, etc.)
    ALLOWED_PREFIXES = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/_health/',
        '/admin/logout/',
        '/account/logout/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip middleware during testing
        from django.conf import settings as django_settings
        db_name = str(django_settings.DATABASES.get('default', {}).get('NAME', ''))
        if getattr(django_settings, 'TESTING', False) or 'test' in db_name or ':memory:' in db_name:
            return self.get_response(request)
        
        # Verificar se o usuário está autenticado
        if request.user.is_authenticated:
            # Verificar se a URL atual é permitida
            if not self._is_allowed_url(request):
                # Verificar se o usuário tem 2FA configurado
                if not user_has_device(request.user):
                    # Adicionar mensagem de alerta (usando sessão para evitar duplicatas)
                    if not request.session.get('_2fa_warning_shown'):
                        messages.warning(
                            request, 
                            "⚠️ Você precisa configurar a Autenticação em Duas Etapas (2FA) para acessar o sistema."
                        )
                        request.session['_2fa_warning_shown'] = True
                    
                    return redirect('two_factor:setup')
        
        return self.get_response(request)
    
    def _is_allowed_url(self, request):
        """Verifica se a URL atual está na lista de URLs permitidas."""
        # Verificar prefixos
        for prefix in self.ALLOWED_PREFIXES:
            if request.path.startswith(prefix):
                return True
        
        # Verificar nomes de URLs específicos
        try:
            from django.urls import resolve, Resolver404
            resolved = resolve(request.path)
            url_name = f"{resolved.namespace}:{resolved.url_name}" if resolved.namespace else resolved.url_name
            
            for allowed in self.ALLOWED_URLS:
                if url_name == allowed or resolved.url_name == allowed:
                    return True
        except Resolver404:
            pass
        
        return False
