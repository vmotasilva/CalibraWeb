# -*- coding: utf-8 -*-
"""
Helper functions and utilities for views migration.
Este arquivo contém funções utilitárias e helpers compartilhadas entre os módulos.
Será importado por cada módulo que precisar dessas funcionalidades.
"""

import io
import os
import re
import zipfile
from datetime import date, datetime, timedelta
import tempfile
from decimal import Decimal
import unicodedata
import logging
import pandas as pd

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, Http404
from django.db.models import Q, Count, Max, Prefetch
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files import File

logger = logging.getLogger(__name__)


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def excel_date_to_datetime(serial):
    """
    Converte data em formato Excel (serial number ou string) para datetime.
    
    Args:
        serial: Número serial Excel ou string de data
        
    Returns:
        datetime.date ou None
    """
    if pd.isnull(serial) or str(serial).strip() == "" or str(serial).strip() == "-":
        return None
    try:
        serial_str = str(serial).strip()
        if "/" in serial_str:
            return pd.to_datetime(serial_str, dayfirst=True).date()
        serial_float = float(serial)
        return (datetime(1899, 12, 30) + timedelta(days=serial_float)).date()
    except:
        return None


def get_all_subordinates(colaborador):
    """
    Retorna um SET com os IDs de todos os subordinados (diretos e indiretos)
    de um colaborador, descendo toda a árvore hierárquica.
    
    Args:
        colaborador: Objeto Colaborador
        
    Returns:
        set: IDs dos subordinados
    """
    subordinados = set()
    diretos = colaborador.liderados.all()
    for direto in diretos:
        subordinados.add(direto.id)
        subordinados.update(get_all_subordinates(direto))
    return subordinados


def get_colaborador_for_user(user):
    """
    Retorna o objeto Colaborador associado a um usuário Django.
    
    Args:
        user: User object
        
    Returns:
        Colaborador ou None
    """
    from rh.models import Colaborador
    
    if not user.is_authenticated:
        return None
    
    try:
        col = Colaborador.objects.get(user_django=user)
        return col
    except Colaborador.DoesNotExist:
        pass
    except Exception:
        pass

    def norm(s: str) -> str:
        if not s:
            return ""
        s = unicodedata.normalize('NFD', s)
        s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
        s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip().upper()
        return s

    fn = (user.first_name or "").strip()
    ln = (user.last_name or "").strip()

    # 2) FIRST+LAST iexact
    if fn and ln:
        nome_montado = f"{fn} {ln}".strip()
        c = Colaborador.objects.filter(nome_completo__iexact=nome_montado).first()
        if c:
            try:
                if c.user_django_id is None:
                    c.user_django = user
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c

    # 3) prefixo/sufixo ignorando acentos
    if fn and ln:
        fn_n = norm(fn)
        ln_n = norm(ln)
        candidatos = []
        for c in Colaborador.objects.all().only("id", "nome_completo"):
            nc = norm(c.nome_completo)
            if nc.startswith(fn_n + " ") and nc.endswith(" " + ln_n):
                candidatos.append(c)
        if len(candidatos) == 1:
            c = candidatos[0]
            try:
                if c.user_django_id is None:
                    c.user_django = user
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c

    # 4) username == matricula
    if user.username:
        c = Colaborador.objects.filter(matricula__iexact=user.username).first()
        if c:
            try:
                if c.user_django_id is None:
                    c.user_django = user
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c
    
    return None


def dl_generic(cols, fname):
    """
    Cria e faz download de um arquivo Excel genérico com colunas específicas.
    
    Args:
        cols: Lista de nomes de colunas
        fname: Nome do arquivo para download
        
    Returns:
        HttpResponse com arquivo Excel
    """
    df = pd.DataFrame(columns=cols)
    return dl_df(df, fname)


def dl_df(df, fname):
    """
    Faz download de um DataFrame como arquivo Excel.
    
    Args:
        df: pandas DataFrame
        fname: Nome do arquivo para download
        
    Returns:
        HttpResponse com arquivo Excel
    """
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


def can_manage_procedimentos(user):
    """
    Verifica se usuário pode gerenciar procedimentos.
    
    Args:
        user: User object
        
    Returns:
        bool: True se pode gerenciar procedimentos
    """
    from rh.models import Colaborador, HierarquiaSetor
    
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    
    try:
        col = Colaborador.objects.filter(user_django=user).select_related('setor').first()
        if col and col.setor and any(k in col.setor.nome.upper() for k in ['QUALIDADE','RH','ENGENHARIA']):
            return True
    except Exception:
        pass
    return False


# ==============================================================================
# REPORTLAB IMPORTS (para PDFs)
# ==============================================================================

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, letter, portrait, landscape
    from reportlab.lib.colors import HexColor as RColor
    from PyPDF2 import PdfReader, PdfWriter
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab or PyPDF2 not available. PDF features will be limited.")


def export_to_excel_response(rows, filename):
    """
    Exporta lista de dicionários para Excel e retorna HttpResponse.
    
    Args:
        rows: Lista de dicionários
        filename: Nome do arquivo
        
    Returns:
        HttpResponse com arquivo Excel
    """
    b = io.BytesIO()
    df = pd.DataFrame(rows)
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)
    r = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r['Content-Disposition'] = f'attachment; filename="{filename}"'
    return r


def parse_date(val, dayfirst=True):
    """
    Converte valor para data.
    
    Args:
        val: Valor a converter
        dayfirst: Se True, interpreta DD/MM/YYYY
        
    Returns:
        datetime.date ou None
    """
    if not val or str(val).lower() == 'nan':
        return None
    try:
        return pd.to_datetime(val, dayfirst=dayfirst).date()
    except Exception:
        return None
