"""
Middleware de controle de acesso por módulo.
Protege automaticamente views de módulos específicos sem precisar adicionar
decorators individuais em cada view.
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve
from shared.permissions import has_module_access, MODULES_PERMISSIONS


class ModuleAccessMiddleware:
    """
    Middleware que verifica permissão de módulo para cada request.
    
    Funciona verificando a URL da requisição e identificando o módulo.
    Se o usuário não tiver acesso, redireciona para página de acesso negado.
    """
    
    # Mapeamento de prefixos de URL para módulos
    URL_TO_MODULE_MAPPING = {
        '/metrologia/': 'metrologia',
        '/rh/': 'rh',
        '/procedures/': 'procedures',
        '/fornecedores/': 'fornecedores',
        '/acoes/': 'acoes',
        '/auditoria/': 'auditoria',
        '/procurements/': 'procurements',
        '/admin/': 'admin',  # Admin não é restringido
    }
    
    # URLs públicas que não requerem verificação
    PUBLIC_URLS = [
        '/',
        '/accounts/',
        '/login/',
        '/logout/',
        '/acesso-negado/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar permissão de módulo
        self.check_module_access(request)
        
        response = self.get_response(request)
        return response

    def check_module_access(self, request):
        """
        Verifica se o usuário tem acesso ao módulo da URL.
        """
        # Usuários não autenticados passam (redirecionados por @login_required depois)
        if not request.user.is_authenticated:
            return
        
        # Superusers e staff têm acesso a tudo
        if request.user.is_superuser or request.user.is_staff:
            return
        
        # URLs públicas não precisam de verificação
        if any(request.path.startswith(url) for url in self.PUBLIC_URLS):
            return
        
        # Encontrar o módulo pela URL
        module_key = self._get_module_from_url(request.path)
        
        if module_key and module_key != 'admin':
            # Verificar acesso
            if not has_module_access(request.user, module_key):
                # Armazenar mensagem na sessão
                messages.error(
                    request,
                    f"❌ Acesso negado! Você não tem permissão para acessar o módulo '{module_key}'."
                )
                # Redirecionar para página de acesso negado
                request.session.save()
                request.access_denied_redirect = redirect('access_denied', module=module_key)

    def _get_module_from_url(self, path):
        """
        Extrai o módulo a partir do caminho da URL.
        """
        for url_prefix, module in self.URL_TO_MODULE_MAPPING.items():
            if path.startswith(url_prefix):
                return module
        
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Hook do middleware para processar antes da view.
        """
        if hasattr(request, 'access_denied_redirect'):
            return request.access_denied_redirect
        return None
