# -*- coding: utf-8 -*-
"""
Middlewares compartilhados para o CalibraWeb.
"""
from .auth_no_cache import AuthNoCacheMiddleware
from .two_factor_required import TwoFactorRequiredMiddleware
from .module_access import ModuleAccessMiddleware
from .auto_login import AutoLoginMiddleware

__all__ = ['AuthNoCacheMiddleware', 'TwoFactorRequiredMiddleware', 'ModuleAccessMiddleware', 'AutoLoginMiddleware']
