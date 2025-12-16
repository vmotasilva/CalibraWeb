"""
Decorators para controle de acesso baseado em módulos.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from shared.permissions import get_module_key, has_module_access


def require_module_access(view_func):
    """
    Decorator que verifica se o usuário tem acesso ao módulo da view.
    Se não tiver acesso, redireciona para página de acesso negado com alerta.
    
    Uso:
    @require_module_access
    def minha_view(request, ...):
        ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Usuários anônimos são redirecionados para login
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Obter o módulo da view
        module_key = get_module_key(view_func.__module__)
        
        # Verificar acesso
        if not has_module_access(request.user, module_key):
            messages.error(
                request, 
                f"❌ Acesso negado! Você não tem permissão para acessar o módulo '{module_key}'."
            )
            return redirect('access_denied', module=module_key)
        
        # Permitir acesso
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_modules_access(*module_keys):
    """
    Decorator que verifica acesso a múltiplos módulos.
    O usuário precisa ter acesso a pelo menos um dos módulos.
    
    Uso:
    @require_modules_access('metrologia', 'rh')
    def minha_view(request, ...):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Verificar se tem acesso a pelo menos um módulo
            has_access = any(
                has_module_access(request.user, module) 
                for module in module_keys
            )
            
            if not has_access:
                modules_str = ', '.join(module_keys)
                messages.error(
                    request,
                    f"❌ Acesso negado! Você não tem permissão para acessar nenhum desses módulos: {modules_str}"
                )
                return redirect('access_denied', module='')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator
