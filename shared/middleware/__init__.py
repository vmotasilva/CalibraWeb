# -*- coding: utf-8 -*-
"""
Middlewares compartilhados para o CalibraWeb.
"""
from .two_factor_required import TwoFactorRequiredMiddleware

__all__ = ['TwoFactorRequiredMiddleware']
