from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.conf import settings

class AutoLoginMiddleware:
    """
    Middleware para ambiente de desenvolvimento (DEBUG=True) que faz o login automático 
    do primeiro superusuário encontrado para agilizar o processo.
    """
    # login() rotaciona o token CSRF; fazer isso antes do CsrfViewMiddleware
    # invalida o formulario de login (403 no POST), entao nao interferimos nelas.
    SKIP_PREFIXES = ('/logout/', '/admin/logout/', '/account/', '/admin/login/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'DEBUG', False) and not request.user.is_authenticated:
            if request.method != 'GET' or request.path.startswith(self.SKIP_PREFIXES):
                return self.get_response(request)

            user = User.objects.filter(is_superuser=True, is_active=True).first()
            if user:
                # Isentar o usuário do 2FA se não estiver isento
                group, _ = Group.objects.get_or_create(name='Isentos 2FA')
                if not user.groups.filter(name='Isentos 2FA').exists():
                    user.groups.add(group)

                # Autenticar
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                
        return self.get_response(request)
