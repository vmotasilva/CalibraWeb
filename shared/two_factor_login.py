# -*- coding: utf-8 -*-
"""Login com 2FA que respeita o grupo 'Isentos 2FA' (nao pede o codigo do autenticador)."""
from two_factor.views import LoginView

GRUPO_ISENTOS_2FA = 'Isentos 2FA'


def _usuario_isento(user):
    return bool(user) and user.groups.filter(name=GRUPO_ISENTOS_2FA).exists()


class LoginViewIsentos2FA(LoginView):
    def has_token_step(self):
        return not _usuario_isento(self.get_user()) and super().has_token_step()

    def has_backup_step(self):
        return not _usuario_isento(self.get_user()) and super().has_backup_step()

    condition_dict = {
        LoginView.TOKEN_STEP: has_token_step,
        LoginView.BACKUP_STEP: has_backup_step,
    }
