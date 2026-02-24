# -*- coding: utf-8 -*-
"""
Views compartilhadas - Dashboard, Health Check, Templates e Admin
"""

import io
import os
import tempfile
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from django.db.models import Q
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Imports dos models
from metrologia.models import Instrumento
from procedures.models import ProcessoCotacao, RegistroTreinamento
from rh.models import Colaborador
from organization.models import CentroCusto
from qms.models import SolicitacaoInstrumento, ImportJob

# Imports dos helpers
from qms.views_helpers import dl_df, dl_generic, parse_date


# ==============================================================================
# DASHBOARD E HEALTH CHECK
# ==============================================================================

@login_required
@login_required
def home_view(request):
    """Página inicial com boas-vindas ao usuário."""
    from shared.notifications import get_user_cobrancas_items

    cobrancas_items = get_user_cobrancas_items(request.user)
    total_cobrancas = sum(item.count for item in cobrancas_items)

    return render(
        request,
        "shared/home.html",
        {
            "cobrancas_items": cobrancas_items,
            "total_cobrancas": total_cobrancas,
        },
    )


def dashboard_view(request):
    """Dashboard principal agregando dados de todos os módulos."""
    nome_display = request.user.username
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)

    # Metrologia
    qtd_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=hoje, ativo=True
    ).count()
    qtd_avencer = Instrumento.objects.filter(
        data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True
    ).count()
    lista_urgentes = Instrumento.objects.filter(
        data_proxima_calibracao__lte=trinta_dias, ativo=True
    ).order_by("data_proxima_calibracao")[:5]

    # Procurements
    qtd_pendentes = SolicitacaoInstrumento.objects.filter(status="PENDENTE").count()

    ctx = {
        "nome_display": nome_display,
        "qtd_vencidos": qtd_vencidos,
        "qtd_avencer": qtd_avencer,
        "lista_urgentes": lista_urgentes,
        "qtd_cotacoes": ProcessoCotacao.objects.filter(status="ABERTO").count(),
        "qtd_pendentes": qtd_pendentes,
        "today": hoje,
    }
    return render(request, "shared/dashboard.html", ctx)


def health_check(request):
    """Lightweight health check endpoint for monitoring."""
    return HttpResponse("OK", content_type="text/plain")


# ==============================================================================
# DOWNLOAD DE TEMPLATES
# ==============================================================================

@login_required
def dl_template_instr(request):
    """Template para importação de instrumentos com exemplos."""
    from datetime import date, timedelta
    
    exemplo_data = {
        "TAG": ["INS-001", "INS-002", "INS-003"],
        "EQUIPAMENTO": ["Paquímetro Digital", "Micrômetro", "Termômetro Digital"],
        "STATUS": ["ATIVO", "ATIVO", "INATIVO"],
        "FABRICANTE": ["Mitutoyo", "Starrett", "Fluke"],
        "MODELO": ["CD-6", "436B", "51-2"],
        "N SERIE": ["123456", "789012", "345678"],
        "SETOR": ["PRODUÇÃO", "QUALIDADE", "LABORATÓRIO"],
        "LOCALIZACAO": ["Sala 01", "Sala 02", "Sala 03"],
        "FREQUENCIA_MESES": ["12", "12", "6"],
        "DATA_ULTIMA_CALIBRACAO": [
            (date.today() - timedelta(days=30)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=60)).strftime("%d/%m/%Y"),
            (date.today() - timedelta(days=180)).strftime("%d/%m/%Y"),
        ],
        "FAIXA": ["0-150", "0-25", "-50 a 50"],
        "UNIDADE": ["mm", "mm", "°C"],
    }
    
    df = pd.DataFrame(exemplo_data)
    return dl_df(df, "template_instrumentos_v2.xlsx")


@login_required
def dl_template_colab(request):
    """Template para importação de colaboradores com exemplos."""
    return dl_df(
        pd.DataFrame(
            {
                "MATRICULA": ["100", "101", "102"],
                "NOME": ["João Silva", "Maria Santos", "Pedro Costa"],
                "CPF": ["123.456.789-00", "987.654.321-11", "555.666.777-88"],
                "CARGO": ["Operador", "Supervisor", "Gerente"],
                "GRUPO": ["OPERAÇÃO", "SUPERVISÃO", "GESTÃO"],
                "SETOR": ["PRODUÇÃO", "QUALIDADE", "PRODUÇÃO"],
                "CC": ["100", "200", "300"],
                "TURNO": ["INTEGRAL", "INTEGRAL", "INTEGRAL"],
                "STATUS": ["ATIVO", "ATIVO", "AFASTADO"],
                "MAT_LIDER": ["999", "999", "999"],
                "MAT_SUPERVISOR": ["888", "888", "888"],
                "MAT_GERENTE": ["777", "777", "777"],
            }
        ),
        "template_colaboradores.xlsx",
    )


@login_required
def dl_template_hierarquia(request):
    """Template para importação de hierarquia com exemplos."""
    return dl_df(
        pd.DataFrame(
            {
                "SETOR": ["PRODUÇÃO", "QUALIDADE", "LABORATÓRIO"],
                "TURNO": ["TURNO 1", "TURNO 1", "INTEGRAL"],
                "MAT_LIDER": ["100", "101", "102"],
                "MAT_SUPERVISOR": ["103", "104", "105"],
                "MAT_GERENTE": ["106", "106", "106"],
                "MAT_DIRETOR": ["999", "999", "999"],
            }
        ),
        "template_hierarquia.xlsx",
    )


@login_required
def dl_template_historico(request):
    """Template para importação de históricos de calibração."""
    return dl_generic(
        [
            "TAG",
            "FAIXA",
            "UNIDADE DE MEDIDA",
            "DATA CALIBRAÇÃO",
            "DATA APROVAÇÃO",
            "N CERTIFICADO",
            "CAMINHO DO CERTIFICADO",
            "ERRO ENCONTRADO",
            "INCERTEZA",
            "TOLERANCIA PROCESSO (+/-)",
            "RBC (SIM/NAO)",
            "RESULTADO",
            "FORNECEDOR",
            "RESPONSÁVEL",
            "OBSERVAÇÕES",
        ],
        "template_historico.xlsx",
    )


@login_required
def dl_template_ferias(request):
    """Template para importação de férias com exemplos."""
    from datetime import date, timedelta
    
    hoje = date.today()
    df = pd.DataFrame(
        {
            "MATRICULA": ["100", "101", "102"],
            "AQUISITIVO_INICIO": [
                "01/01/2024",
                "01/01/2024",
                "01/06/2024",
            ],
            "AQUISITIVO_FIM": [
                "31/12/2024",
                "31/12/2024",
                "31/05/2025",
            ],
            "DATA_INICIO": [
                (hoje + timedelta(days=30)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=60)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=90)).strftime("%d/%m/%Y"),
            ],
            "DATA_FIM": [
                (hoje + timedelta(days=45)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=75)).strftime("%d/%m/%Y"),
                (hoje + timedelta(days=105)).strftime("%d/%m/%Y"),
            ],
            "STATUS": ["PROGRAMADAS", "GOZADAS", "PROGRAMADAS"],
        }
    )
    return dl_df(df, "template_ferias.xlsx")


@login_required
def dl_template_categorias(request):
    """Template para importação de categorias."""
    df = pd.DataFrame(
        {
            "nome": ["PAQUIMETROS", "MICROMETROS", "TORQUIMETROS"],
            "descricao": [
                "Instrumentos do tipo paquímetro",
                "Instrumentos do tipo micrômetro",
                "Instrumentos para torque",
            ],
            "unidade_sigla": ["mm", "mm", "Nm"],
        }
    )
    return dl_df(df, "template_categorias.xlsx")


@login_required
def dl_template_procedimentos(request):
    """Template para importação de procedimentos."""
    cols = [
        'no', 'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
        'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
        'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
    ]
    exemplo = {
        'no': ['1'],
        'codigo': ['POP.001'],
        'nome': ['EXEMPLO DE PROCEDIMENTO'],
        'descricao': ['Objetivo ou função do procedimento'],
        'pasta': ['QUALIDADE'],
        'classificacao': ['POP'],
        'autor': ['João da Silva'],
        'numero_revisao': ['01'],
        'ultima_revisao': ['01/10/2025'],
        'data_aprovacao': ['05/10/2025'],
        'proxima_revisao': ['05/10/2026'],
        'data_validade': ['05/10/2026'],
        'documentos_controlados': ['Sim'],
        'matriz': ['Matriz A'],
        'sub_area': ['Subárea 1'],
    }
    df = pd.DataFrame({col: exemplo.get(col, ['']) for col in cols})
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r['Content-Disposition'] = 'attachment; filename="template_procedimentos.xlsx"'
    return r


@login_required
def dl_template_colab_dados(request):
    """Exporta dados completos dos colaboradores ativos."""
    # Define permissão para visualizar salário
    colab = None
    try:
        colab = Colaborador.objects.filter(user_django=request.user).first()
    except Exception:
        pass
    
    can_see_salary = False
    if request.user.is_superuser or request.user.is_staff:
        can_see_salary = True
    elif colab:
        if colab.setor and "RH" in colab.setor.nome.upper():
            can_see_salary = True

    # Busca colaboradores ativos
    qs = Colaborador.objects.filter(is_active=True).select_related(
        "setor", "centro_custo", "lider", "supervisor", "gerente"
    ).order_by("nome_completo")

    # Monta dados
    data = []
    for colab in qs:
        data.append(
            {
                "MATRICULA": colab.matricula,
                "NOME": colab.nome_completo,
                "CPF": colab.cpf or "",
                "CARGO": colab.cargo or "",
                "GRUPO": colab.grupo or "Geral",
                "SETOR": colab.setor.nome if colab.setor else "",
                "CC": colab.centro_custo.codigo if colab.centro_custo else "",
                "TURNO": colab.get_turno_display(),
                "TURNO_CODIGO": colab.turno,
                "STATUS": "ATIVO",
                "MAT_LIDER": colab.lider.matricula if colab.lider else "",
                "NOME_LIDER": colab.lider.nome_completo if colab.lider else "",
                "MAT_SUPERVISOR": colab.supervisor.matricula if colab.supervisor else "",
                "NOME_SUPERVISOR": colab.supervisor.nome_completo if colab.supervisor else "",
                "MAT_GERENTE": colab.gerente.matricula if colab.gerente else "",
                "NOME_GERENTE": colab.gerente.nome_completo if colab.gerente else "",
                "EM_FERIAS": "SIM" if colab.em_ferias else "NÃO",
                "SALARIO": (float(colab.salario) if (can_see_salary and colab.salario) else ""),
            }
        )

    df = pd.DataFrame(data)
    fname = f"colaboradores_export_{date.today().strftime('%Y%m%d')}.xlsx"

    b = io.BytesIO()
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)

    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


# ==============================================================================
# GERENCIAMENTO DE JOBS DE IMPORTAÇÃO
# ==============================================================================

@login_required
def import_jobs_view(request):
    """Lista jobs de importação com filtros opcionais."""
    try:
        status = (request.GET.get('status') or '').upper()
        job_type = (request.GET.get('type') or '').upper()
        qs = ImportJob.objects.all()
        
        if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
            qs = qs.filter(status=status)
        if job_type:
            qs = qs.filter(job_type__iexact=job_type)
        
        jobs = list(qs.order_by('-created_at')[:100])
        
        # Prepara dados para exibição
        prepared = []
        for j in jobs:
            summary = j.result or ''
            samples = []
            try:
                if summary and '| Samples:' in summary:
                    parts = summary.split('| Samples:')
                    summary = parts[0].strip()
                    samples_str = parts[1].strip() if len(parts) > 1 else ''
                    if samples_str:
                        samples = [s.strip() for s in samples_str.split(',') if s.strip()]
            except Exception:
                samples = []
            
            prepared.append({
                'id': j.id,
                'job_type': j.job_type,
                'filename': j.filename,
                'status': j.status,
                'result_summary': summary,
                'result_samples': samples,
                'created_at': j.created_at,
                'updated_at': j.updated_at,
                'filepath': j.filepath,
            })
        
        return render(request, 'shared/imports/import_jobs.html', {
            'jobs': prepared,
            'status': status,
            'job_type': job_type,
        })
    except Exception as e:
        return HttpResponse(f"<pre>Falha ao carregar import-jobs: {str(e)}</pre>", 
                          content_type="text/html", status=200)


@login_required
def import_jobs_json_view(request):
    """Retorna jobs de importação em JSON."""
    status = (request.GET.get('status') or '').upper()
    job_type = (request.GET.get('type') or '').upper()
    qs = ImportJob.objects.all()
    
    if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
        qs = qs.filter(status=status)
    if job_type:
        qs = qs.filter(job_type__iexact=job_type)
    
    jobs = qs.order_by('-created_at')[:100]
    data = []
    for j in jobs:
        data.append({
            'id': str(j.id),
            'job_type': j.job_type,
            'filename': j.filename,
            'status': j.status,
            'result': j.result,
            'created_at': j.created_at.isoformat() if j.created_at else None,
            'updated_at': j.updated_at.isoformat() if j.updated_at else None,
            'filepath': j.filepath,
        })
    return JsonResponse({'jobs': data})


@login_required
def retry_import_job_view(request, job_id):
    """Reprocessa um job de importação falho."""
    from qms.tasks import (
        import_instruments_task, import_historico_task, import_colab_task,
        import_hierarquia_task, import_ferias_task
    )
    
    job = get_object_or_404(ImportJob, id=job_id)
    if not job.filepath:
        messages.error(request, "Este job não tem arquivo associado para reprocessar.")
        return redirect('import_jobs')

    try:
        if job.job_type == 'INSTRUMENTOS':
            try:
                import_instruments_task.delay(str(job.id), job.filepath)
            except Exception:
                import_instruments_task(job.id, job.filepath)
        elif job.job_type == 'HISTORICO':
            try:
                import_historico_task.delay(str(job.id), job.filepath)
            except Exception:
                import_historico_task(job.id, job.filepath)
        elif job.job_type == 'RH_COLAB':
            try:
                import_colab_task.delay(str(job.id), job.filepath)
            except Exception:
                import_colab_task(job.id, job.filepath)
        elif job.job_type == 'RH_HIERARQUIA':
            try:
                import_hierarquia_task.delay(str(job.id), job.filepath)
            except Exception:
                import_hierarquia_task(job.id, job.filepath)
        elif job.job_type == 'RH_FERIAS':
            try:
                import_ferias_task.delay(str(job.id), job.filepath)
            except Exception:
                import_ferias_task(job.id, job.filepath)
        else:
            messages.error(request, "Tipo de job não suportado para retry.")
            return redirect('import_jobs')
        
        messages.success(request, f"Reprocessando job {job.id} ({job.job_type}).")
    except Exception as e:
        messages.error(request, f"Falha ao reprocessar: {e}")
    
    return redirect('import_jobs')


# ==============================================================================
# ADMIN UTILITIES
# ==============================================================================

@login_required
def seed_demo_view(request):
    """Dispara seed de dados demo (apenas para staff)."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('dashboard')
    
    try:
        call_command('seed_demo')
        messages.success(request, 'Base de demonstração carregada com sucesso!')
    except Exception as e:
        messages.error(request, f'Falha ao gerar dados de demonstração: {e}')
    
    return redirect('modulo_rh')


@login_required
def fix_historico_proxima_view(request):
    """Recalcula datas de próxima calibração (apenas para staff)."""
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('dashboard')
    
    try:
        recalc = bool(request.GET.get('recalc'))
        call_command('fix_historico_proxima', recalc=recalc)
        messages.success(request, 'Recalculo de próxima calibração concluído!')
    except Exception as e:
        messages.error(request, f'Falha no recalculo: {e}')
    
    return redirect('modulo_metrologia')
