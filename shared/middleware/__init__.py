# -*- coding: utf-8 -*-
"""
Middlewares compartilhados para o CalibraWeb.
"""
from .two_factor_required import TwoFactorRequiredMiddleware
from .module_access import ModuleAccessMiddleware

__all__ = ['TwoFactorRequiredMiddleware', 'ModuleAccessMiddleware']
