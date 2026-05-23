# -*- coding: utf-8 -*-
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(user_logged_in)
def set_session_expiry(sender, request, user, **kwargs):
    """
    Define a expiração da sessão baseada no cookie 'trusted_machine'.
    Se 'trusted_machine' estiver presente e com valor '1', a sessão dura 30 dias.
    Caso contrário, a sessão expira ao fechar o navegador (set_expiry(0)).
    """
    if request and hasattr(request, 'COOKIES'):
        is_trusted = request.COOKIES.get('trusted_machine') == '1'
        if is_trusted:
            # 30 dias em segundos: 30 * 24 * 3600 = 2592000
            request.session.set_expiry(2592000)
            logger.info(f"Session expiry set to 30 days for user {user.username} (Trusted Machine checked)")
        else:
            request.session.set_expiry(0)
            logger.info(f"Session expiry set to 0 (browser close) for user {user.username} (Trusted Machine not checked)")
