from __future__ import annotations

import json
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from django_otp.plugins.otp_totp.models import TOTPDevice


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


@login_required
@require_POST
def api_change_password(request):
    """Troca a senha do usuário logado.

    Espera JSON:
    - current_password
    - new_password
    - confirm_password
    """
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    current_password = (data.get('current_password') or '').strip()
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not current_password or not new_password or not confirm_password:
        return JsonResponse({'success': False, 'error': 'Preencha todos os campos.'}, status=400)

    if new_password != confirm_password:
        return JsonResponse({'success': False, 'error': 'As senhas novas não conferem.'}, status=400)

    user = request.user
    if not user.check_password(current_password):
        return JsonResponse({'success': False, 'error': 'Senha atual incorreta.'}, status=400)

    try:
        validate_password(new_password, user=user)
    except Exception as e:
        errors = getattr(e, 'messages', None)
        msg = errors[0] if errors else 'Senha nova inválida.'
        return JsonResponse({'success': False, 'error': msg}, status=400)

    user.set_password(new_password)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)

    return JsonResponse({'success': True, 'message': 'Senha alterada com sucesso.'})


@require_POST
def api_reset_password_totp(request):
    """Reseta a senha a partir do código do autenticador (TOTP) registrado.

    Espera JSON:
    - username (ou email)
    - otp_code (6 dígitos)
    - new_password
    - confirm_password
    """
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    identifier = (data.get('username') or '').strip()
    otp_code = (data.get('otp_code') or '').strip().replace(' ', '')
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not identifier or not otp_code or not new_password or not confirm_password:
        return JsonResponse({'success': False, 'error': 'Preencha todos os campos.'}, status=400)

    if new_password != confirm_password:
        return JsonResponse({'success': False, 'error': 'As senhas novas não conferem.'}, status=400)

    if not otp_code.isdigit() or len(otp_code) != 6:
        return JsonResponse({'success': False, 'error': 'Código inválido. Use 6 dígitos.'}, status=400)

    User = get_user_model()

    user = None
    if '@' in identifier:
        user = User.objects.filter(email__iexact=identifier, is_active=True).first()
    if user is None:
        user = User.objects.filter(username__iexact=identifier, is_active=True).first()

    if user is None:
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    devices = TOTPDevice.objects.filter(user=user, confirmed=True)
    if not devices.exists():
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    token_int = int(otp_code)
    is_valid = False
    for device in devices:
        try:
            if device.verify_token(token_int):
                is_valid = True
                break
        except Exception:
            continue

    if not is_valid:
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    try:
        validate_password(new_password, user=user)
    except Exception as e:
        errors = getattr(e, 'messages', None)
        msg = errors[0] if errors else 'Senha nova inválida.'
        return JsonResponse({'success': False, 'error': msg}, status=400)

    user.set_password(new_password)
    user.save(update_fields=['password'])

    return JsonResponse({'success': True, 'message': 'Senha redefinida com sucesso. Você já pode entrar.'})


@csrf_exempt
@require_GET
def run_cron_tasks(request):
    """
    HTTP endpoint to trigger periodic tasks in serverless environment (Vercel).
    Protected by CRON_SECRET token via Authorization Header (Bearer) or secret query param.
    """
    secret = request.GET.get('secret')
    auth_header = request.headers.get('authorization')
    expected_secret = os.getenv('CRON_SECRET')
    
    authorized = False
    if expected_secret:
        if secret == expected_secret:
            authorized = True
        elif auth_header == f"Bearer {expected_secret}":
            authorized = True
            
    if not authorized:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

        
    results = {}
    
    # 1. Update status of delayed actions
    try:
        from acoes.tasks import atualizar_status_acoes_atrasadas
        results['acoes_atrasadas'] = atualizar_status_acoes_atrasadas()
    except Exception as e:
        results['acoes_atrasadas'] = {'error': str(e)}
        
    # 2. Update status of vacations
    try:
        from rh.tasks.ferias_tasks import atualizar_status_ferias_logic, sincronizar_em_ferias
        results['ferias_status'] = atualizar_status_ferias_logic()
        results['ferias_sincronizacao'] = sincronizar_em_ferias()
    except Exception as e:
        results['ferias_tasks'] = {'error': str(e)}
        
    return JsonResponse({'success': True, 'results': results})

