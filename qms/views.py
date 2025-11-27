import io
import os
import re
import zipfile
from datetime import date, datetime, timedelta
import tempfile
from decimal import Decimal
import unicodedata

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import IntegrityError, models, transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import Http404, HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.colors import Color as RColor
from reportlab.pdfgen import canvas

# IMPORTA OS FORMS
from .forms import (CarimboForm, ColaboradorForm, ImportacaoColaboradoresForm,
                    ImportacaoFeriasForm, ImportacaoHierarquiaForm,
                    ImportacaoHistoricoForm, ImportacaoInstrumentosForm,
                    ImportacaoPadroesForm, ImportacaoProcedimentosForm,
                    OcorrenciaForm, SolicitacaoForm)
# IMPORTA TODOS OS MODELOS
from .models import (CategoriaInstrumento, CentroCusto, Colaborador,
                     FaixaMedicao, Ferias, Fornecedor, HierarquiaSetor,
                     HistoricoCalibracao, Instrumento, Ocorrencia,
                     OrdemCalibracao, Padrao, Procedimento, ProcessoCotacao,
                     RegistroTreinamento, Setor, SolicitacaoInstrumento,
                     UnidadeMedida, ImportJob)
from django.views.decorators.http import require_POST


# --- FUNÇÕES AUXILIARES ---
def get_colab(request):
    """
    Mapeia o usuário Django logado para um Colaborador.
    Ordem:
      1) vínculo direto em `user_django`
      2) FIRST+LAST iexact com `nome_completo`
      3) FIRST como prefixo e LAST como sufixo (ignorando acentos/caixa)
      4) fallback por `username` == `matricula`
    Se encontrar um único Colaborador e o vínculo estiver vazio, salva `user_django`.
    """
    u = request.user
    # 1) vínculo direto
    try:
        col = Colaborador.objects.get(user_django=u)
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

    fn = (u.first_name or "").strip()
    ln = (u.last_name or "").strip()

    # 2) FIRST+LAST iexact
    if fn and ln:
        nome_montado = f"{fn} {ln}".strip()
        c = Colaborador.objects.filter(nome_completo__iexact=nome_montado).first()
        if c:
            # vincula se possível
            try:
                if c.user_django_id is None:
                    c.user_django = u
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
                    c.user_django = u
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c

    # 4) username == matricula
    if u.username:
        c = Colaborador.objects.filter(matricula__iexact=u.username).first()
        if c:
            try:
                if c.user_django_id is None:
                    c.user_django = u
                    c.save(update_fields=["user_django"])
            except Exception:
                pass
            return c
    return None


def excel_date_to_datetime(serial):
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
    """
    subordinados = set()
    diretos = colaborador.liderados.all()
    for direto in diretos:
        subordinados.add(direto.id)
        subordinados.update(get_all_subordinates(direto))
    return subordinados


# ==============================================================================
# VIEWS DE TELA (DASHBOARD E MÓDULOS)
# ==============================================================================


@login_required
def dashboard_view(request):
    colab = get_colab(request)
    nome_display = colab.nome_completo if colab else request.user.username
    hoje = date.today()
    trinta_dias = hoje + timedelta(days=30)

    qtd_vencidos = Instrumento.objects.filter(
        data_proxima_calibracao__lt=hoje, ativo=True
    ).count()
    qtd_avencer = Instrumento.objects.filter(
        data_proxima_calibracao__range=[hoje, trinta_dias], ativo=True
    ).count()
    lista_urgentes = Instrumento.objects.filter(
        data_proxima_calibracao__lte=trinta_dias, ativo=True
    ).order_by("data_proxima_calibracao")[:5]

    # NOVO: Contagem de solicitações pendentes
    qtd_pendentes = SolicitacaoInstrumento.objects.filter(status="PENDENTE").count()

    ctx = {
        "colaborador": colab,
        "nome_display": nome_display,
        "qtd_vencidos": qtd_vencidos,
        "qtd_avencer": qtd_avencer,
        "lista_urgentes": lista_urgentes,
        "qtd_cotacoes": ProcessoCotacao.objects.filter(status="ABERTO").count(),
        "qtd_pendentes": qtd_pendentes,  # <--- Adicionado ao contexto
        "today": hoje,
    }
    return render(request, "dashboard.html", ctx)


@login_required
def modulo_metrologia_view(request):
    colab = get_colab(request)

    # Busca todos os instrumentos
    instrumentos = Instrumento.objects.filter(ativo=True).select_related('categoria','setor').order_by("tag")

    # --- NOVA LÓGICA DE FILTRO VINDO DO DASHBOARD ---
    status_filter = request.GET.get("status")  # Pega o parâmetro da URL
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)

    if status_filter == "vencidos":
        # Filtra onde a data é menor que hoje
        instrumentos = instrumentos.filter(data_proxima_calibracao__lt=hoje)
        messages.info(request, "Exibindo apenas instrumentos VENCIDOS.")

    elif status_filter == "avencer":
        # Filtra no intervalo entre hoje e 30 dias
        instrumentos = instrumentos.filter(
            data_proxima_calibracao__range=[hoje, alerta_30d]
        )
        messages.info(request, "Exibindo instrumentos a vencer em 30 dias.")

    # Preparação dos Filtros (Extraindo valores únicos presentes na lista)
    setores_ids = instrumentos.values_list("setor", flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by("nome")

    categorias_ids = instrumentos.values_list("categoria", flat=True).distinct()
    categorias_filtro = CategoriaInstrumento.objects.filter(
        id__in=categorias_ids
    ).order_by("nome")

    # Datas de referência para o template calcular status (Vencido/A Vencer)
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)

    ctx = {
        "colaborador": colab,
        "instrumentos": instrumentos,
        "setores_filtro": setores_filtro,
        "categorias_filtro": categorias_filtro,
        "hoje": hoje,
        "alerta_30d": alerta_30d,
        "can_edit": True,
    }
    return render(request, "modulo_metrologia.html", ctx)


@login_required
def export_metrologia_view(request):
    """Exporta os instrumentos (respeitando filtros por querystring) para Excel."""
    q = (request.GET.get('q') or '').strip().lower()
    st = set((request.GET.get('st') or '').split(',')) if request.GET.get('st') else set()
    sit = set((request.GET.get('sit') or '').split(',')) if request.GET.get('sit') else set()
    cat = set((request.GET.get('cat') or '').split(',')) if request.GET.get('cat') else set()
    st_setor = set((request.GET.get('set') or '').split(',')) if request.GET.get('set') else set()

    qs = Instrumento.objects.all().select_related('categoria','setor').prefetch_related('faixas','faixas__unidade')
    if st:
        if 'ATIVO' in st and 'INATIVO' not in st:
            qs = qs.filter(ativo=True)
        elif 'INATIVO' in st and 'ATIVO' not in st:
            qs = qs.filter(ativo=False)
    if cat:
        try:
            cat_ids = [int(x) for x in cat if x.isdigit()]
            qs = qs.filter(categoria_id__in=cat_ids)
        except Exception:
            pass
    if st_setor:
        try:
            setor_ids = [int(x) for x in st_setor if x.isdigit()]
            qs = qs.filter(setor_id__in=setor_ids)
        except Exception:
            pass
    if q:
        qs = qs.filter(models.Q(tag__icontains=q) | models.Q(descricao__icontains=q) | models.Q(fabricante__icontains=q) | models.Q(modelo__icontains=q))

    # Situação (vencido/avencer/em_dia) é derivada de datas - filtra após fetch
    hoje = date.today()
    alerta_30d = hoje + timedelta(days=30)
    rows = []
    for inst in qs:
        situacao = 'EM_DIA'
        if inst.data_proxima_calibracao:
            if inst.data_proxima_calibracao < hoje:
                situacao = 'VENCIDO'
            elif inst.data_proxima_calibracao <= alerta_30d:
                situacao = 'AVENCER'
        if sit and situacao not in sit:
            continue
        unidade = ''
        try:
            fx = inst.faixas.all().first()
            if fx and fx.unidade:
                unidade = fx.unidade.sigla
        except Exception:
            unidade = ''
        rows.append({
            'TAG': inst.tag,
            'DESCRICAO': inst.descricao,
            'CATEGORIA': inst.categoria.nome if inst.categoria else '',
            'SETOR': inst.setor.nome if inst.setor else '',
            'FABRICANTE': inst.fabricante or '',
            'MODELO': inst.modelo or '',
            'SERIE': inst.serie or '',
            'SITUACAO': situacao,
            'ULTIMA_CALIB': inst.data_ultima_calibracao.strftime('%Y-%m-%d') if inst.data_ultima_calibracao else '',
            'PROXIMA_CALIB': inst.data_proxima_calibracao.strftime('%Y-%m-%d') if inst.data_proxima_calibracao else '',
            'UNIDADE': unidade,
        })
    import pandas as pd
    import io
    b = io.BytesIO()
    df = pd.DataFrame(rows)
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)
    r = HttpResponse(b, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r['Content-Disposition'] = 'attachment; filename="instrumentos_export.xlsx"'
    return r


@login_required
def modulo_rh_view(request):
    colab = get_colab(request)

    # 1. VISIBILIDADE (quem pode ver TODOS e quem vê sua árvore)
    ids_permitidos = set()
    can_see_salary = False

    can_view_all = False
    if request.user.is_superuser:
        can_view_all = True
    elif colab:
        setor_nome = (colab.setor.nome.upper() if colab.setor else "")
        if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
            can_view_all = True
        elif (
            "GERENTE" in str(colab.cargo).upper()
            or HierarquiaSetor.objects.filter(gerente=colab).exists()
        ):
            can_view_all = True

    if can_view_all:
        ids_permitidos = set(Colaborador.objects.all().values_list("id", flat=True))
    elif colab:
        # Inclui subordinados diretos (por relação de líder) e a própria pessoa
        ids_permitidos = get_all_subordinates(colab)
        ids_permitidos.add(colab.id)
        # Também inclui quem o usuário lidera/supervisiona/gerencia diretamente
        diretos = Colaborador.objects.filter(
            Q(lider=colab) | Q(supervisor=colab) | Q(gerente=colab)
        ).values_list('id', flat=True)
        ids_permitidos.update(diretos)
    else:
        ids_permitidos = set()

    # Regra 2.2: salário/CPF apenas para superusuários, gerentes e diretores
    if request.user.is_superuser:
        can_see_salary = True
    elif colab:
        if "GERENTE" in str(colab.cargo).upper() or \
           HierarquiaSetor.objects.filter(gerente=colab).exists() or \
           ("DIRETOR" in str(colab.cargo).upper()) or \
           HierarquiaSetor.objects.filter(diretor=colab).exists():
            can_see_salary = True

    # QuerySet BASE: inclui ativos e desligados; filtro por ids_permitidos
    funcionarios_base = Colaborador.objects.filter(
        id__in=list(ids_permitidos)
    ).select_related('setor', 'centro_custo', 'lider', 'supervisor', 'gerente').prefetch_related('treinamentos', 'treinamentos__procedimento').order_by("nome_completo")

    # 2. CÁLCULO DAS OPÇÕES DE FILTRO - BASEADO APENAS NA BASE DE DADOS DE COLABORADORES
    
    # Setores: Pega todos os setores únicos dos colaboradores visíveis
    setores_ids = funcionarios_base.exclude(setor__isnull=True).values_list("setor", flat=True).distinct()
    setores_filtro = Setor.objects.filter(id__in=setores_ids).order_by("nome")

    # Líderes: Pega todos os líderes únicos dos colaboradores visíveis
    lideres_ids = funcionarios_base.exclude(lider__isnull=True).values_list("lider", flat=True).distinct()
    lideres_filtro = Colaborador.objects.filter(id__in=lideres_ids).order_by("nome_completo")

    # Supervisores: Pega todos os supervisores únicos dos colaboradores visíveis
    supervisores_ids = funcionarios_base.exclude(supervisor__isnull=True).values_list("supervisor", flat=True).distinct()
    supervisores_filtro = Colaborador.objects.filter(id__in=supervisores_ids).order_by("nome_completo")

    # Gerentes: Pega todos os gerentes únicos dos colaboradores visíveis
    gerentes_ids = funcionarios_base.exclude(gerente__isnull=True).values_list("gerente", flat=True).distinct()
    gerentes_filtro = Colaborador.objects.filter(id__in=gerentes_ids).order_by("nome_completo")

    # Turnos: Pega todos os turnos únicos dos colaboradores visíveis
    turnos_unicos = funcionarios_base.values_list("turno", flat=True).distinct()
    # Usa choices do próprio modelo para evitar depender de constantes globais
    turnos_map = dict(Colaborador._meta.get_field('turno').choices)
    turnos_filtro = [(turno, turnos_map.get(turno, turno)) for turno in turnos_unicos if turno]

    # 3. RESULTADO FINAL
    funcionarios_visiveis = funcionarios_base

    # 4. Estatísticas de Treinamento por colaborador (pendentes/vigentes, última data)
    for f in funcionarios_visiveis:
        vig = 0
        pend = 0
        last = None
        for rt in getattr(f, 'treinamentos').all():
            if rt.status_treinamento == "VIGENTE":
                vig += 1
            else:
                pend += 1
            if rt.data_treinamento and (last is None or rt.data_treinamento > last):
                last = rt.data_treinamento
        # Atribui no próprio objeto para fácil acesso no template
        f.trein_vigentes = vig
        f.trein_pendentes = pend
        f.trein_ultima_data = last

    ctx = {
        "colaborador": colab,
        "funcionarios": funcionarios_visiveis,
        "lideres_filtro": lideres_filtro,
        "setores_filtro": setores_filtro,
        "supervisores_filtro": supervisores_filtro,
        "gerentes_filtro": gerentes_filtro,
        "turnos_filtro": turnos_filtro,
        "centros": CentroCusto.objects.all().order_by("codigo"),
        "can_see_salary": can_see_salary,
        "can_edit": True,
    }
    return render(request, "modulo_rh.html", ctx)


@login_required
def procedimentos_list_view(request):
    """Lista pública (pós-login) de procedimentos com filtros simples.
    Parâmetros GET:
      q: termo de busca (código ou parte do título)
      tipo: prefixo (POP, DOC, FOR, TAB, DEX)
    """
    termo = (request.GET.get("q") or "").strip().upper()
    tipo = (request.GET.get("tipo") or "").strip().upper()

    qs = Procedimento.objects.all().select_related("setor")
    if termo:
        qs = qs.filter(models.Q(codigo__icontains=termo) | models.Q(titulo__icontains=termo))
    if tipo in {"POP", "DOC", "FOR", "TAB", "DEX"}:
        qs = qs.filter(codigo__startswith=f"{tipo}.")

    # Limita para paginação simples (pode evoluir depois)
    # Paginação
    from django.core.paginator import Paginator
    page_number = request.GET.get("page", "1")
    paginator = Paginator(qs.order_by("codigo"), 50)
    page_obj = paginator.get_page(page_number)
    procedimentos = page_obj.object_list

    tipos_stats = {
        t: Procedimento.objects.filter(codigo__startswith=f"{t}.").count()
        for t in ["POP", "DOC", "FOR", "TAB", "DEX"]
    }

    ctx = {
        "procedimentos": procedimentos,
        "termo": termo,
        "tipo": tipo,
        "tipos_stats": tipos_stats,
        "page_obj": page_obj,
        "paginator": paginator,
        "querystring_base": f"q={termo}&tipo={tipo}" if (termo or tipo) else "",
    }
    return render(request, "procedimentos_lista.html", ctx)


@login_required
def detalhe_colaborador_view(request, colab_id):
    usuario_logado = get_colab(request)
    alvo = get_object_or_404(Colaborador, id=colab_id)

    # --- NOVO: BUSCA DE HIERARQUIA POR SETOR/TURNO (para visualização) ---
    supervisor_rh = None
    gerente_rh = None

    if alvo.setor and alvo.turno:
        # Tenta encontrar a hierarquia exata para Setor e Turno
        hierarquia = HierarquiaSetor.objects.filter(
            setor=alvo.setor, turno=alvo.turno
        ).first()

        # Se não encontrar no turno específico, tenta o turno ADM como fallback
        if not hierarquia:
            hierarquia = HierarquiaSetor.objects.filter(
                setor=alvo.setor, turno="ADM"
            ).first()

        if hierarquia:
            supervisor_rh = hierarquia.supervisor
            gerente_rh = hierarquia.gerente

    # Segurança: pode ver todos se for superuser, gerente, RH/DP/Qualidade
    if not request.user.is_superuser:
        permitido = False
        if usuario_logado:
            setor_nome = (usuario_logado.setor.nome.upper() if usuario_logado.setor else "")
            pode_ver_todos = False
            if any(k in setor_nome for k in ["RH", "DP", "QUALIDADE"]):
                pode_ver_todos = True
            if ("GERENTE" in str(usuario_logado.cargo).upper() or
                HierarquiaSetor.objects.filter(gerente=usuario_logado).exists()):
                pode_ver_todos = True
            if pode_ver_todos:
                permitido = True
            elif usuario_logado.id == alvo.id:
                permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados:
                    permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect("modulo_rh")

    # Regra 2.2: salário/CPF apenas para superusuários, gerentes e diretores
    can_see_salary = False
    if request.user.is_superuser:
        can_see_salary = True
    elif usuario_logado:
        if ("GERENTE" in str(usuario_logado.cargo).upper() or
            HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or
            ("DIRETOR" in str(usuario_logado.cargo).upper()) or
            HierarquiaSetor.objects.filter(diretor=usuario_logado).exists()):
            can_see_salary = True

    # Permissões específicas para Ocorrências de RH
    can_register_occ = False
    can_view_occ = False
    if request.user.is_superuser or request.user.is_staff:
        can_register_occ = True
        can_view_occ = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            can_register_occ = True
            can_view_occ = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            can_register_occ = True
            can_view_occ = True
        # O próprio colaborador pode ver a página, mas não vê ocorrências
        if usuario_logado.id == alvo.id and not (request.user.is_superuser or request.user.is_staff):
            can_view_occ = False

    ocorrencias = alvo.ocorrencias.all().order_by("-data_ocorrencia") if can_view_occ else []
    treinamentos = alvo.treinamentos.all().order_by("-data_treinamento")
    documentos = alvo.documentos_pessoais.all().order_by("-data_upload")

    # Férias
    try:
        ferias_qs = alvo.ferias_set.all().order_by("-periodo_aquisitivo_fim")
    except AttributeError:
        ferias_qs = []

    ferias_vencidas = 0
    ferias_programadas = 0
    hoje = date.today()

    for f in ferias_qs:
        dt_limite = (
            f.data_limite
            if f.data_limite
            else (
                f.periodo_aquisitivo_fim + timedelta(days=365)
                if f.periodo_aquisitivo_fim
                else None
            )
        )

        if dt_limite and dt_limite < hoje:
            if f.status != "GOZADAS" and (not f.data_inicio or f.data_inicio < hoje):
                ferias_vencidas += 1

        if f.data_inicio and f.data_inicio > hoje:
            ferias_programadas += 1

    ctx = {
        "colaborador": usuario_logado,
        "alvo": alvo,
        "can_see_salary": can_see_salary,
        "can_register_occ": can_register_occ,
        "can_view_occ": can_view_occ,
        "ocorrencias": ocorrencias,
        "treinamentos": treinamentos,
        "documentos": documentos,
        "ferias": ferias_qs,
        "kpi_ferias_vencidas": ferias_vencidas,
        "kpi_ferias_programadas": ferias_programadas,
        "can_edit": True,
        "supervisor_rh": supervisor_rh,  # <--- ENVIADO PARA O TEMPLATE
        "gerente_rh": gerente_rh,  # <--- ENVIADO PARA O TEMPLATE
    }
    return render(request, "detalhe_colaborador.html", ctx)


@login_required
def editar_colaborador_view(request, colab_id):
    usuario_logado = get_colab(request)
    alvo = get_object_or_404(Colaborador, id=colab_id)

    if not (request.user.is_superuser or request.user.is_staff):
        permitido = False
        if usuario_logado:
            if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
                permitido = True
            else:
                meus_subordinados = get_all_subordinates(usuario_logado)
                if alvo.id in meus_subordinados:
                    permitido = True
        if not permitido:
            messages.error(request, "Acesso Negado.")
            return redirect("modulo_rh")

    if request.method == "POST":
        form = ColaboradorForm(request.POST, instance=alvo)
        if form.is_valid():
            form.save()
            messages.success(request, "Atualizado!")
            return redirect("detalhe_colaborador", colab_id=alvo.id)
        else:
            messages.error(request, "Erro ao salvar.")
    else:
        form = ColaboradorForm(instance=alvo)
    return render(
        request,
        "editar_colaborador.html",
        {"form": form, "alvo": alvo, "colaborador": usuario_logado},
    )


# --- REGISTRO DE OCORRÊNCIA DO COLABORADOR ---
@login_required
def registrar_ocorrencia_view(request):
    # Permissão: apenas RH, liderança (supervisor/gerente) e staff/superuser podem registrar
    usuario_logado = get_colab(request)
    permitido = False
    if request.user.is_superuser or request.user.is_staff:
        permitido = True
    elif usuario_logado:
        if usuario_logado.setor and "RH" in usuario_logado.setor.nome.upper():
            permitido = True
        if HierarquiaSetor.objects.filter(gerente=usuario_logado).exists() or \
           HierarquiaSetor.objects.filter(supervisor=usuario_logado).exists():
            permitido = True
    if not permitido:
        messages.error(request, "Você não tem permissão para registrar ocorrências.")
        return redirect("modulo_rh")

    preselect_id = request.GET.get("colab_id")
    if request.method == "POST":
        form = OcorrenciaForm(request.POST, request.FILES)
        if form.is_valid():
            oc = form.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            if oc.colaborador_id:
                return redirect("detalhe_colaborador", colab_id=oc.colaborador_id)
            return redirect("modulo_rh")
        else:
            messages.error(request, "Verifique os dados da ocorrência.")
    else:
        initial = {}
        if preselect_id:
            initial["colaborador"] = preselect_id
        form = OcorrenciaForm(initial=initial)
    return render(
        request,
        "registro_ocorrencia.html",
        {"form": form, "colaborador": get_colab(request)},
    )


# --- NOVA VIEW: SOLICITAÇÃO DE INSTRUMENTO ---
@login_required
def nova_solicitacao(request):
    if request.method == "POST":
        form = SolicitacaoForm(request.POST)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.solicitante = request.user
            solicitacao.save()
            messages.success(request, "Solicitação enviada com sucesso!")
            return redirect("home")  # Volta para o dashboard
    else:
        form = SolicitacaoForm()

    return render(
        request,
        "form_generico.html",
        {"form": form, "titulo": "Nova Solicitação", "colaborador": get_colab(request)},
    )


# --- VIEW ATUALIZADA: DETALHE DO INSTRUMENTO (COM OCORRÊNCIAS E ORDENS) ---
@login_required
def detalhe_instrumento_view(
    request, instrumento_id
):  # Note que o URLs.py usa 'pk' ou 'instrumento_id', verifique se o urls.py espera <int:pk> ou <int:instrumento_id>. Vou manter instrumento_id conforme seu código antigo.
    inst = get_object_or_404(Instrumento, id=instrumento_id)

    # Processamento do Form de Ocorrência Rápida
    if request.method == "POST":
        form_ocorrencia = OcorrenciaForm(request.POST)
        if form_ocorrencia.is_valid():
            ocorrencia = form_ocorrencia.save(commit=False)
            ocorrencia.instrumento = inst
            ocorrencia.usuario_responsavel = request.user
            ocorrencia.save()
            messages.success(request, "Ocorrência registrada com sucesso!")
            # Recarrega a página para limpar o post
            return redirect("detalhe_instrumento", instrumento_id=inst.id)
        else:
            messages.error(request, "Erro ao registrar ocorrência. Verifique os dados.")
    else:
        form_ocorrencia = OcorrenciaForm()

    # Buscando dados para as novas abas
    try:
        historico = inst.historico_calibracoes.all().order_by("-data_calibracao")
    except AttributeError:
        # Fallback caso tenha mudado
        historico = []

    # Usando related_names definidos no models.py (calibracoes e ocorrencias)
    # Se der erro aqui, verifique se no models.py está related_name='calibracoes'
    try:
        calibracoes = inst.calibracoes.all().order_by("-data_prevista")
    except AttributeError:
        calibracoes = []  # Fallback caso a migration não tenha rolado 100%

    try:
        ocorrencias = inst.ocorrencias.all().order_by("-data_ocorrencia")
    except AttributeError:
        ocorrencias = []

    # Anexa atributo responsavel_colab_id às ocorrências quando houver vínculo com Colaborador
    try:
        for oc in ocorrencias:
            u = getattr(oc, "usuario_responsavel", None)
            if u:
                col = Colaborador.objects.filter(user_django=u).only("id").first()
                if col:
                    setattr(oc, "responsavel_colab_id", col.id)
    except Exception:
        pass

    try:
        faixas = inst.faixamedicao_set.all()
    except AttributeError:
        ocorrencias = []

    if hasattr(inst, "faixas"):
        faixas = inst.faixas.all()

    return render(
        request,
        "detalhe_instrumento.html",
        {
            "colaborador": get_colab(request),
            "instrumento": inst,
            "historico": historico,
            "calibracoes": calibracoes,
            "ocorrencias": ocorrencias,
            # nenhuma var extra necessária: cada ocorrência pode ter atributo responsavel_colab_id
            "faixas": faixas,
            "form_ocorrencia": form_ocorrencia,
            "today": date.today(),
        },
    )


@login_required
def remover_historico_view(request, historico_id):
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    i_id = hist.instrumento.id
    if hist.certificado:
        hist.certificado.delete(save=False)
    hist.delete()
    messages.success(request, "Removido.")
    return redirect("detalhe_instrumento", instrumento_id=i_id)


@login_required
def anexar_certificado_historico_view(request, historico_id):
    """Anexa um arquivo PDF ao registro de histórico que ainda não tenha certificado."""
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    inst_id = hist.instrumento.id if hist.instrumento else None
    if request.method != "POST":
        messages.error(request, "Método inválido.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    if hist.certificado:
        messages.warning(request, "Este histórico já possui certificado anexado.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    up = request.FILES.get("certificado_pdf")
    if not up:
        messages.error(request, "Selecione um arquivo PDF para anexar.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    # Validação simples de tipo
    ctype = getattr(up, "content_type", "") or ""
    if "pdf" not in ctype.lower():
        messages.error(request, "Arquivo inválido. Envie um PDF.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    # Salva no campo FileField; o nome ficará em certificados/
    try:
        filename = f"Cert_{hist.numero_certificado}_{hist.instrumento.tag}.pdf" if hist.instrumento else up.name
        hist.certificado.save(filename, up, save=True)
        messages.success(request, "Certificado anexado com sucesso!")
    except Exception as e:
        messages.error(request, f"Falha ao anexar certificado: {e}")
    return redirect("detalhe_instrumento", instrumento_id=inst_id)


@login_required
def remover_certificado_historico_view(request, historico_id):
    """Remove apenas o arquivo de certificado do histórico, mantendo o registro."""
    hist = get_object_or_404(HistoricoCalibracao, id=historico_id)
    inst_id = hist.instrumento.id if hist.instrumento else None
    if request.method != "POST":
        messages.error(request, "Método inválido.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    if not hist.certificado:
        messages.warning(request, "Este histórico não possui certificado anexado.")
        return redirect("detalhe_instrumento", instrumento_id=inst_id)

    try:
        hist.certificado.delete(save=False)
        hist.certificado = None
        hist.save(update_fields=["certificado"])
        messages.success(request, "Certificado removido. Você pode anexar um novo.")
    except Exception as e:
        messages.error(request, f"Falha ao remover certificado: {e}")
    return redirect("detalhe_instrumento", instrumento_id=inst_id)


# ==============================================================================
# CARIMBO (VALIDAÇÃO)
# ==============================================================================
@login_required
def carimbar_view(request):
    colab = get_colab(request)
    instrumentos_disponiveis = Instrumento.objects.filter(ativo=True).prefetch_related('faixas').order_by("tag")
    # Prepara dados de tolerância (+/-) por instrumento (primeira faixa com valor)
    instrumentos_data = []
    for inst in instrumentos_disponiveis:
        tol_val = None
        try:
            for fx in inst.faixas.all():
                if getattr(fx, 'tolerancia_mais_menos', None) is not None:
                    tol_val = fx.tolerancia_mais_menos
                    break
        except Exception:
            tol_val = None
        instrumentos_data.append({
            'id': inst.id,
            'tag': inst.tag,
            'descricao': inst.descricao,
            'tolerancia': tol_val,
        })
    user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
    if not user_full_name:
        user_full_name = request.user.username.upper()

    if request.method == "POST":
        form = CarimboForm(request.POST, request.FILES)
        if form.is_valid():
            c_resp = colab
            dt_validacao = form.cleaned_data["data_validacao"]
            status_txt = form.cleaned_data["status_validacao"]
            is_rbc = form.cleaned_data.get("is_rbc", False)
            padroes_selecionados = form.cleaned_data.get("padroes", [])

            # Leitura dos parâmetros de análise (opcionais)
            # Campos E/U/T serão informados por arquivo (por índice) – ver laço abaixo

            # Função auxiliar para parse decimal com vírgula
            def parse_dec(v):
                if v is None or v == "":
                    return None
                try:
                    return Decimal(str(v).replace(',', '.'))
                except Exception:
                    return None

            fs = request.FILES.getlist("arquivo_pdf")
            processed_files = []
            try:
                screen_w = float(request.POST.get("page_width", 0))
                screen_h = float(request.POST.get("page_height", 0))
            except:
                screen_w = 0
                screen_h = 0
            processed_files = []

            for i, f in enumerate(fs):
                raw_x = request.POST.get(f"x_{i}", 0)
                raw_y = request.POST.get(f"y_{i}", 0)
                raw_w = request.POST.get(f"w_{i}", 0)
                raw_h = request.POST.get(f"h_{i}", 0)
                ui = (
                    float(raw_x),
                    float(raw_y),
                    float(raw_w),
                    float(raw_h),
                    screen_w,
                    screen_h,
                )
                inst_id = request.POST.get(f"instrument_id_{i}")
                calib_date_str = request.POST.get(f"calib_date_{i}")
                cert_num = request.POST.get(f"cert_num_{i}", f.name)

                if inst_id and calib_date_str:
                    try:
                        instrumento = Instrumento.objects.get(id=inst_id)
                        dt_calibracao = datetime.strptime(
                            calib_date_str, "%Y-%m-%d"
                        ).date()
                        prox_calib = None
                        if instrumento.frequencia_meses:
                            prox_calib = dt_calibracao + timedelta(
                                days=instrumento.frequencia_meses * 30
                            )

                        # Lê E/U/T por arquivo e calcula o resultado deste item
                        erro_in = parse_dec(request.POST.get(f"err_{i}"))
                        inc_in = parse_dec(request.POST.get(f"inc_{i}"))
                        tol_in = parse_dec(request.POST.get(f"tol_{i}"))
                        # Fallback: se tolerância não informada, usa a do instrumento (primeira faixa disponível)
                        if tol_in is None:
                            try:
                                for fx in instrumento.faixas.all():
                                    v = getattr(fx, 'tolerancia_mais_menos', None)
                                    if v is not None:
                                        tol_in = Decimal(str(v))
                                        break
                            except Exception:
                                tol_in = None

                        status_item = status_txt
                        resultado_item = "APROVADO"
                        if erro_in is not None and inc_in is not None and tol_in is not None:
                            try:
                                ema = abs(tol_in) / Decimal(2)
                                eme = abs(erro_in) + abs(inc_in)
                                if eme <= ema:
                                    resultado_item = "APROVADO"
                                    status_item = "Aprovado sem correções"
                                elif eme > (ema * Decimal(3)):
                                    resultado_item = "REPROVADO"
                                    status_item = "Reprovado"
                                else:
                                    resultado_item = "CONDICIONAL"
                                    status_item = "Aprovado com correções"
                            except Exception:
                                pass
                        else:
                            if status_item == "Reprovado":
                                resultado_item = "REPROVADO"
                            elif status_item == "Aprovado com correções":
                                resultado_item = "CONDICIONAL"

                        hist, created = HistoricoCalibracao.objects.get_or_create(
                            instrumento=instrumento,
                            data_calibracao=dt_calibracao,
                            numero_certificado=cert_num,
                            defaults={
                                "proxima_calibracao": prox_calib,
                                "resultado": resultado_item,
                                "responsavel": str(c_resp),
                                "observacoes": f"Validado por {user_full_name}: {status_item}",
                                "tem_selo_rbc": is_rbc,
                                "tipo_calibracao": "EXTERNA",
                            },
                        )
                        # Preenche dados numéricos quando houverem
                        if erro_in is not None:
                            hist.erro_encontrado = erro_in
                        if inc_in is not None:
                            hist.incerteza = inc_in
                        if tol_in is not None:
                            hist.tolerancia_usada = tol_in

                        if not created:
                            hist.resultado = resultado_item
                            hist.observacoes = f"Revalidado: {status_item}"
                        if not is_rbc and padroes_selecionados:
                            hist.padroes_utilizados.set(padroes_selecionados)
                        # Gera PDF com carimbo usando o status calculado para ESTE item
                        pdf_buffer = apply_stamp_logic(
                            f, user_full_name, status_item, ui, dt_validacao
                        )
                        filename = f"Cert_{cert_num}_{instrumento.tag}.pdf"
                        hist.certificado.save(
                            filename, ContentFile(pdf_buffer.getvalue())
                        )
                        hist.save()
                    except Exception as e:
                        print(f"Erro: {e}")
                # Adiciona saída para download em lote (usa o buffer gerado)
                if inst_id and calib_date_str:
                    try:
                        pdf_buffer.seek(0)
                        processed_files.append((f.name, pdf_buffer))
                    except Exception:
                        processed_files.append((f.name, io.BytesIO()))

            if len(processed_files) == 1:
                fname, fbuf = processed_files[0]
                r = HttpResponse(fbuf, content_type="application/pdf")
                r["Content-Disposition"] = f'attachment; filename="Validado_{fname}"'
                return r
            elif len(processed_files) > 1:
                zb = io.BytesIO()
            with zipfile.ZipFile(zb, "w") as zf:
                for fname, fbuf in processed_files:
                    zf.writestr(f"Validado_{fname}", fbuf.getvalue())
            zb.seek(0)
            r = HttpResponse(zb, content_type="application/zip")
            r["Content-Disposition"] = 'attachment; filename="Lote_Validados.zip"'
            return r
    else:
        form = CarimboForm()
    return render(
        request,
        "carimbo.html",
        {
            "form": form,
            "colaborador": colab,
            "user_full_name": user_full_name,
            "instrumentos": instrumentos_disponiveis,
            "instrumentos_data": instrumentos_data,
        },
    )


def apply_stamp_logic(f, user_name, status, ui, data_validacao):
    ipdf = PdfReader(f)
    o = PdfWriter()
    if len(ipdf.pages) > 0:
        p = ipdf.pages[0]
        try:
            pdf_w = float(p.mediabox.width)
            pdf_h = float(p.mediabox.height)
        except:
            pdf_w = 595.0
            pdf_h = 842.0
        screen_x, screen_y, screen_box_w, screen_box_h, screen_w, screen_h = ui
        if screen_w > 0 and screen_h > 0:
            scale_x = pdf_w / screen_w
            scale_y = pdf_h / screen_h
            final_x = screen_x * scale_x
            final_y = pdf_h - (screen_y * scale_y) - (screen_box_h * scale_y)
        else:
            final_x = pdf_w - 150
            final_y = 50
        b = io.BytesIO()
        c = canvas.Canvas(b, pagesize=(pdf_w, pdf_h))
        if "Reprovado" in status:
            main_color = RColor(0.8, 0, 0)
        else:
            main_color = RColor(0, 0.5, 0)
        c.setFillColor(main_color)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(final_x, final_y + 20, status)
        c.setFillColor(RColor(0, 0, 0))
        c.setFont("Helvetica", 9)
        c.drawString(final_x, final_y + 10, f"{data_validacao.strftime('%d/%m/%Y')}")
        c.drawString(final_x, final_y, f"{user_name}")
        c.save()
        b.seek(0)
        st = PdfReader(b)
        p.merge_page(st.pages[0])
        o.add_page(p)
        for pg in ipdf.pages[1:]:
            o.add_page(pg)
    out = io.BytesIO()
    o.write(out)
    out.seek(0)
    return out


# --- DOWNLOAD DE TEMPLATES ---
def dl_template_instr(request):
    return dl_generic(
        [
            "TAG",
            "EQUIPAMENTO",
            "STATUS",
            "FABRICANTE",
            "MODELO",
            "N SERIE",
            "SETOR",
            "LOCALIZACAO",
            "FREQUENCIA_MESES",
            "DATA_ULTIMA_CALIBRACAO",
            "FAIXA",
            "UNIDADE",
        ],
        "template_instrumentos_v2.xlsx",
    )


def dl_template_colab(request):
    return dl_df(
        pd.DataFrame(
            {
                "MATRICULA": ["100"],
                "NOME": ["TESTE"],
                "CPF": ["000"],
                "CARGO": ["Y"],
                "GRUPO": ["ADM"],
                "SETOR": ["ADM"],
                "CC": ["100"],
                "TURNO": ["ADM"],
                "STATUS": ["ATIVO"],
                "MAT_LIDER": ["999"],
                "MAT_SUPERVISOR": ["888"],
                "MAT_GERENTE": ["777"],
            }
        ),
        "template_colaboradores.xlsx",
    )


def dl_template_hierarquia(request):
    return dl_df(
        pd.DataFrame(
            {
                "SETOR": ["MAN"],
                "TURNO": ["T1"],
                "MAT_LIDER": ["1"],
                "MAT_SUPERVISOR": [""],
                "MAT_GERENTE": [""],
                "MAT_DIRETOR": [""],
            }
        ),
        "template_hierarquia.xlsx",
    )


def dl_template_historico(request):
    return dl_generic(
        [
            "TAG",
            "DATA CALIBRAÇÃO",
            "DATA APROVAÇÃO",
            "N CERTIFICADO",
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


# --- NOVO TEMPLATE DE FÉRIAS ---
def dl_template_ferias(request):
    df = pd.DataFrame(
        {
            "MATRICULA": ["100"],
            "AQUISITIVO_INICIO": ["01/01/2023"],
            "AQUISITIVO_FIM": ["31/12/2023"],
            "DATA_INICIO": ["10/02/2024"],
            "DATA_FIM": ["20/02/2024"],
            "STATUS": ["PROGRAMADAS"],
        }
    )
    return dl_df(df, "template_ferias.xlsx")


def dl_generic(cols, fname):
    df = pd.DataFrame(columns=cols)
    return dl_df(df, fname)


def dl_df(df, fname):
    b = io.BytesIO()
    df.to_excel(b, index=False)
    b.seek(0)
    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


# --- IMPORTAÇÕES COMPLETAS (SEM CORTES) ---


@login_required
def imp_instr_view(request):
    if request.method == "POST":
        form = ImportacaoInstrumentosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                # create import job record
                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="INSTRUMENTOS",
                    status="PENDING",
                )

                # Execução síncrona forçada se SYNC_IMPORTS=1 (default) ou se Celery falhar
                from .tasks import import_instruments_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_instruments_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação enfileirada (job {job.id}).")
                        return redirect("modulo_metrologia")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_instruments_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Importação concluída imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_instrumentos")
    else:
        form = ImportacaoInstrumentosForm()
    return render(
        request,
        "importar_instrumentos.html",
        {"form": form, "colaborador": get_colab(request), "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


@login_required
def imp_historico_view(request):
    if request.method == "POST":
        form = ImportacaoHistoricoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="HISTORICO",
                    status="PENDING",
                )

                from .tasks import import_historico_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_historico_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação histórico enfileirada (job {job.id}).")
                        return redirect("modulo_metrologia")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_historico_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Histórico importado imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro ao enfileirar importação: {str(e)}")
                return redirect("importar_historico")
    else:
        form = ImportacaoHistoricoForm()
    return render(
        request,
        "importar_historico.html",
        {"form": form, "colaborador": get_colab(request), "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


@login_required
def imp_padroes_view(request):
    if request.method == "POST":
        form = ImportacaoPadroesForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                f = request.FILES["arquivo_excel"]
                try:
                    df = pd.read_excel(f)
                except:
                    df = pd.read_csv(f, sep=None, engine="python")
                df.columns = df.columns.str.strip().str.upper()
                count = 0
                with transaction.atomic():
                    for _, row in df.iterrows():
                        codigo = str(row.get("CODIGO", "")).strip()
                        if codigo:
                            Padrao.objects.update_or_create(
                                codigo=codigo,
                                defaults={"descricao": "Importado", "ativo": True},
                            )
                            count += 1
                messages.success(request, f"{count} Padrões importados!")
                return redirect("modulo_metrologia")
            except Exception as e:
                messages.error(request, f"Erro: {e}")
    else:
        form = ImportacaoPadroesForm()
    return render(
        request,
        "importar_historico.html",
        {"form": form, "titulo": "Importar Padrões", "colaborador": get_colab(request)},
    )


@login_required
def imp_categorias_view(request):
    """Importa categorias em massa a partir de CSV (nome,descricao,unidade_sigla)."""
    if request.method == 'POST':
        f = request.FILES.get('arquivo')
        if not f:
            messages.error(request, 'Selecione um arquivo CSV.')
            return redirect('importar_categorias')
        import csv, io
        try:
            decoded = io.TextIOWrapper(f.file, encoding='utf-8')
        except Exception:
            decoded = io.TextIOWrapper(f, encoding='utf-8')
        reader = csv.DictReader(decoded)
        created = 0; updated = 0; not_found_units = 0
        for row in reader:
            nome = (row.get('nome') or '').strip()
            if not nome:
                continue
            desc = (row.get('descricao') or '').strip() or None
            unidade_sigla = (row.get('unidade_sigla') or '').strip()
            unidade_obj = None
            if unidade_sigla:
                unidade_obj = UnidadeMedida.objects.filter(sigla__iexact=unidade_sigla).first()
                if not unidade_obj:
                    not_found_units += 1
            obj, was_created = CategoriaInstrumento.objects.update_or_create(
                nome=nome,
                defaults={
                    'descricao': desc,
                    'unidade_padrao': unidade_obj,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
        messages.success(request, f"Categorias criadas: {created}, atualizadas: {updated}. Unidades não encontradas: {not_found_units}")
        return redirect('modulo_metrologia')
    return render(request, 'importar_categorias.html', { 'colaborador': get_colab(request) })


@login_required
def imp_colab_view(request):
    if request.method == "POST":
        form = ImportacaoColaboradoresForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="RH_COLAB",
                    status="PENDING",
                )

                from .tasks import import_colab_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_colab_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de colaboradores enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_colab_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Colaboradores importados imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro na importação: {str(e)}")
                return redirect("modulo_rh")
    else:
        form = ImportacaoColaboradoresForm()
    return render(
        request,
        "importar_colaboradores.html",
        {"form": form, "colaborador": get_colab(request), "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


@login_required
def imp_hierarquia_view(request):
    if request.method == "POST":
        form = ImportacaoHierarquiaForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="RH_HIERARQUIA",
                    status="PENDING",
                )

                from .tasks import import_hierarquia_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_hierarquia_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de hierarquia enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_hierarquia_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Hierarquia importada imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro na importação: {str(e)}")
                return redirect("modulo_rh")
    return render(
        request,
        "importar_hierarquia.html",
        {"form": ImportacaoHierarquiaForm(), "colaborador": get_colab(request), "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


# --- IMPORTAÇÃO DE FÉRIAS (COM DIAS VENDIDOS) ---
@login_required
def imp_ferias_view(request):
    if request.method == "POST":
        form = ImportacaoFeriasForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded = request.FILES["arquivo_excel"]
                suffix = os.path.splitext(uploaded.name)[1] or ".xlsx"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp.flush(); tmp.close()

                job = ImportJob.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    filename=uploaded.name,
                    filepath=tmp.name,
                    job_type="RH_FERIAS",
                    status="PENDING",
                )

                from .tasks import import_ferias_task
                force_sync = os.environ.get("SYNC_IMPORTS", "1") == "1"
                if not force_sync:
                    try:
                        import_ferias_task.delay(str(job.id), tmp.name)
                        messages.success(request, f"Importação de férias enfileirada (job {job.id}).")
                        return redirect("modulo_rh")
                    except Exception:
                        force_sync = True
                if force_sync:
                    import_ferias_task(job.id, tmp.name)
                    job.refresh_from_db()
                    messages.success(request, f"Férias importadas imediatamente (job {job.id}). {job.result or ''}")
                    return redirect("modulo_rh")
            except Exception as e:
                messages.error(request, f"Erro: {e}")
    else:
        form = ImportacaoFeriasForm()
    return render(
        request,
        "importar_ferias.html",
        {"form": form, "colaborador": get_colab(request), "jobs": ImportJob.objects.order_by('-created_at')[:5]},
    )


# Adicione esta função na seção de Downloads de Templates (após dl_df):


@login_required
@login_required
def dl_template_colab_dados(request):
    """Gera um arquivo Excel com dados completos dos Colaboradores ativos."""

    # Define permissão para visualizar salário conforme mesmas regras da tela RH
    colab = get_colab(request)
    can_see_salary = False
    if request.user.is_superuser or request.user.is_staff:
        can_see_salary = True
    elif colab:
        if colab.setor and "RH" in colab.setor.nome.upper():
            can_see_salary = True
        else:
            if (
                "GERENTE" in str(colab.cargo).upper()
                or HierarquiaSetor.objects.filter(gerente=colab).exists()
            ):
                can_see_salary = True

    # 1. Busca todos os colaboradores ativos
    qs = Colaborador.objects.filter(is_active=True).select_related(
        "setor", "centro_custo", "lider", "supervisor", "gerente"
    ).order_by("nome_completo")

    # 2. Cria uma lista de dicionários com os dados
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

    # 3. Cria o DataFrame e o arquivo Excel na memória
    df = pd.DataFrame(data)
    fname = f"colaboradores_export_{date.today().strftime('%Y%m%d')}.xlsx"

    # Reutiliza a função dl_df para servir o arquivo
    b = io.BytesIO()
    df.to_excel(b, index=False, engine='openpyxl')
    b.seek(0)

    r = HttpResponse(
        b,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    r["Content-Disposition"] = f'attachment; filename="{fname}"'
    return r


def health_check(request):
    """Lightweight health check endpoint for monitoring and readiness probes.

    Returns HTTP 200 when Django is running and imports succeeded. This is intentionally
    simple so external systems can check app liveness quickly (eg. Railway/Heroku/Gunicorn).
    """
    from django.http import HttpResponse

    return HttpResponse("OK", content_type="text/plain")


@login_required
def import_jobs_view(request):
    """List recent import jobs with optional status filter."""
    try:
        from .models import ImportJob
        status = (request.GET.get('status') or '').upper()
        job_type = (request.GET.get('type') or '').upper()
        qs = ImportJob.objects.all()
        if status in {'PENDING','STARTED','SUCCESS','FAILURE'}:
            qs = qs.filter(status=status)
        if job_type:
            qs = qs.filter(job_type__iexact=job_type)
        jobs = list(qs.order_by('-created_at')[:100])
        # Prepare display fields: split summary and samples if present
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
        return render(request, 'import_jobs.html', {
            'jobs': prepared,
            'status': status,
            'job_type': job_type,
            'colaborador': get_colab(request),
        })
    except Exception as e:
        # Fallback: return minimal HTML to avoid 500 and expose error
        return HttpResponse(f"<pre>Falha ao carregar import-jobs: {str(e)}</pre>", content_type="text/html", status=200)


@login_required
def import_jobs_json_view(request):
    """Return recent import jobs as JSON for debugging when template fails."""
    from .models import ImportJob
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
    """Retry a failed or pending import job by re-enqueuing its task."""
    from .models import ImportJob
    from .tasks import import_instruments_task, import_historico_task, import_colab_task, import_hierarquia_task, import_ferias_task

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


# --- ADMIN-ONLY: disparar seed de dados demo ---
@login_required
def seed_demo_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('home')
    try:
        from django.core.management import call_command
        call_command('seed_demo')
        messages.success(request, 'Base de demonstração carregada com sucesso!')
    except Exception as e:
        messages.error(request, f'Falha ao gerar dados de demonstração: {e}')
    # retorna ao RH (tem indicadores visuais) por padrão
    return redirect('modulo_rh')


@login_required
def fix_historico_proxima_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Acesso negado.")
        return redirect('home')
    try:
        from django.core.management import call_command
        recalc = bool(request.GET.get('recalc'))
        call_command('fix_historico_proxima', recalc=recalc)
        messages.success(request, 'Recalculo de próxima calibração concluído!')
    except Exception as e:
        messages.error(request, f'Falha no recalculo: {e}')
    return redirect('modulo_metrologia')
