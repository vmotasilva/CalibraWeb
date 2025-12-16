from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def home_view(request):
    return render(request, 'shared/home.html')


def access_denied_view(request, module=''):
    """
    View exibida quando o usuário não tem acesso a um módulo.
    """
    context = {
        'module': module,
        'user': request.user,
    }
    return render(request, 'shared/access_denied.html', context, status=403)
