from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from io import BytesIO
import json

from .forms import ModeloAuditoriaForm, PerguntaAuditoriaForm, RegistroAuditoriaForm
from .models import ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria, RespostaAuditoria


@login_required
def modulo_auditoria_view(request):
    total_modelos = ModeloAuditoria.objects.count()
    total_perguntas = PerguntaAuditoria.objects.count()
    total_registros = RegistroAuditoria.objects.count()
    registros_recentes = RegistroAuditoria.objects.select_related("modelo").order_by("-data_auditoria")[:5]

    context = {
        "total_modelos": total_modelos,
        "total_perguntas": total_perguntas,
        "total_registros": total_registros,
        "registros_recentes": registros_recentes,
    }
    return render(request, "auditoria/modulo_auditoria.html", context)


@login_required
def modelos_list(request):
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    modelos = ModeloAuditoria.objects.annotate(total_perguntas=Count("perguntas"))
    if inicio:
        modelos = modelos.filter(criado_em__date__gte=inicio)
    if fim:
        modelos = modelos.filter(criado_em__date__lte=fim)

    context = {"modelos": modelos.order_by("nome"), "inicio": inicio, "fim": fim}
    return render(request, "auditoria/modelos_list.html", context)


@login_required
def modelo_create(request):
    if request.method == "POST":
        form = ModeloAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de auditoria criado com sucesso.")
            return redirect("auditoria:modelos_list")
    else:
        form = ModeloAuditoriaForm()
    return render(request, "auditoria/modelo_form.html", {"form": form, "modo": "novo"})


@login_required
def modelo_edit(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if request.method == "POST":
        form = ModeloAuditoriaForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de auditoria atualizado com sucesso.")
            return redirect("auditoria:modelos_list")
    else:
        form = ModeloAuditoriaForm(instance=modelo)
    return render(request, "auditoria/modelo_form.html", {"form": form, "modo": "edicao", "modelo": modelo})


@login_required
def modelo_delete(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if request.method == "POST":
        modelo.delete()
        messages.success(request, "Modelo removido com sucesso.")
        return redirect("auditoria:modelos_list")
    return render(request, "auditoria/modelo_confirm_delete.html", {"modelo": modelo})


@login_required
def perguntas_list(request):
    modelo_id = request.GET.get("modelo")
    perguntas = PerguntaAuditoria.objects.select_related("modelo")
    if modelo_id:
        perguntas = perguntas.filter(modelo_id=modelo_id)

    context = {
        "perguntas": perguntas.order_by("modelo__nome", "ordem", "id"),
        "modelos": ModeloAuditoria.objects.filter(ativo=True).order_by("nome"),
        "modelo_id": modelo_id,
    }
    return render(request, "auditoria/perguntas_list.html", context)


@login_required
def pergunta_create(request):
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta cadastrada com sucesso.")
            return redirect("auditoria:perguntas_list")
    else:
        initial = {}
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            initial["modelo"] = modelo_id
        form = PerguntaAuditoriaForm(initial=initial)
    return render(request, "auditoria/pergunta_form.html", {"form": form, "modo": "novo"})


@login_required
def pergunta_edit(request, pk):
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada com sucesso.")
            return redirect("auditoria:perguntas_list")
    else:
        form = PerguntaAuditoriaForm(instance=pergunta)
    return render(request, "auditoria/pergunta_form.html", {"form": form, "modo": "edicao", "pergunta": pergunta})


@login_required
def pergunta_delete(request, pk):
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        pergunta.delete()
        messages.success(request, "Pergunta removida com sucesso.")
        return redirect("auditoria:perguntas_list")
    return render(request, "auditoria/pergunta_confirm_delete.html", {"pergunta": pergunta})


@login_required
def registros_list(request):
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    modelo_id = request.GET.get("modelo")

    registros = RegistroAuditoria.objects.select_related("modelo", "avaliador")
    if inicio:
        registros = registros.filter(data_auditoria__gte=inicio)
    if fim:
        registros = registros.filter(data_auditoria__lte=fim)
    if modelo_id:
        registros = registros.filter(modelo_id=modelo_id)

    context = {
        "registros": registros.order_by("-data_auditoria", "-id"),
        "modelos": ModeloAuditoria.objects.filter(ativo=True).order_by("nome"),
        "inicio": inicio,
        "fim": fim,
        "modelo_id": modelo_id,
    }
    return render(request, "auditoria/registros_list.html", context)


@login_required
def selecionar_modelo_preenchimento(request):
    """Lista modelos ativos para o usuário escolher qual preencher"""
    modelos = ModeloAuditoria.objects.filter(ativo=True).annotate(
        total_perguntas=Count("perguntas", filter=models.Q(perguntas__ativo=True))
    ).order_by("nome")
    
    context = {"modelos": modelos}
    return render(request, "auditoria/selecionar_modelo.html", context)


@login_required
def registro_create(request, modelo_id=None):
    """Cria novo registro de auditoria para um modelo específico"""
    if modelo_id:
        modelo = get_object_or_404(ModeloAuditoria, pk=modelo_id, ativo=True)
    else:
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            modelo = get_object_or_404(ModeloAuditoria, pk=modelo_id, ativo=True)
        else:
            return redirect("auditoria:selecionar_modelo_preenchimento")
    
    perguntas = PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("ordem", "id")
    
    if request.method == "POST":
        form = RegistroAuditoriaForm(request.POST)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.modelo = modelo
            registro.avaliador = request.user
            registro.save()

            # Salvar respostas
            erros = []
            for pergunta in perguntas:
                valor = request.POST.get(f"resposta_{pergunta.id}", "").strip()
                if not valor and pergunta.obrigatoria:
                    erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória.")
                RespostaAuditoria.objects.create(registro=registro, pergunta=pergunta, valor=valor)
            
            if erros:
                for erro in erros:
                    messages.warning(request, erro)
            
            messages.success(request, "Formulário de auditoria preenchido com sucesso!")
            return redirect("auditoria:registro_detail", pk=registro.pk)
    else:
        from datetime import date
        form = RegistroAuditoriaForm(initial={"data_auditoria": date.today()})

    context = {
        "form": form,
        "modelo": modelo,
        "perguntas": perguntas,
    }
    return render(request, "auditoria/registro_form.html", context)


@login_required
def registro_edit(request, pk):
    """Edita um registro de auditoria existente"""
    registro = get_object_or_404(RegistroAuditoria.objects.select_related("modelo"), pk=pk)
    perguntas = PerguntaAuditoria.objects.filter(modelo=registro.modelo, ativo=True).order_by("ordem", "id")
    
    if request.method == "POST":
        form = RegistroAuditoriaForm(request.POST, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.save()

            # Atualizar respostas existentes
            for pergunta in perguntas:
                valor = request.POST.get(f"resposta_{pergunta.id}", "").strip()
                RespostaAuditoria.objects.update_or_create(
                    registro=registro,
                    pergunta=pergunta,
                    defaults={"valor": valor}
                )
            
            messages.success(request, "Registro de auditoria atualizado com sucesso!")
            return redirect("auditoria:registro_detail", pk=registro.pk)
    else:
        form = RegistroAuditoriaForm(instance=registro)
        # Preencher valores atuais das respostas
        respostas_atuais = {}
        for resposta in registro.respostas.all():
            respostas_atuais[resposta.pergunta_id] = resposta.valor

    context = {
        "form": form,
        "modelo": registro.modelo,
        "perguntas": perguntas,
        "registro": registro,
        "respostas_atuais": respostas_atuais,
        "edicao": True,
    }
    return render(request, "auditoria/registro_form.html", context)


@login_required
def registro_detail(request, pk):
    registro = get_object_or_404(
        RegistroAuditoria.objects.select_related("modelo", "avaliador"),
        pk=pk,
    )
    respostas = registro.respostas.select_related("pergunta").order_by("pergunta__ordem", "id")
    total_respostas = respostas.count()
    preenchidas = respostas.exclude(valor="").count()
    percentual_preenchimento = round((preenchidas / total_respostas) * 100, 1) if total_respostas else 0

    context = {
        "registro": registro,
        "respostas": respostas,
        "total_respostas": total_respostas,
        "preenchidas": preenchidas,
        "percentual_preenchimento": percentual_preenchimento,
    }
    return render(request, "auditoria/registro_detail.html", context)


@login_required
def dashboard_auditoria(request):
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")
    modelo_id = request.GET.get("modelo")

    total_modelos = ModeloAuditoria.objects.count()
    registros = RegistroAuditoria.objects.select_related("modelo")

    if modelo_id:
        registros = registros.filter(modelo_id=modelo_id)
    if inicio:
        registros = registros.filter(data_auditoria__gte=inicio)
    if fim:
        registros = registros.filter(data_auditoria__lte=fim)

    total_registros = registros.count()

    por_modelo = list(
        registros.values("modelo__nome", "modelo__id")
        .annotate(total=Count("id"))
        .order_by("-total", "modelo__nome")
    )

    por_periodicidade_raw = list(
        registros.values("modelo__periodicidade")
        .annotate(total=Count("id"))
        .order_by("modelo__periodicidade")
    )

    periodicidade_map = dict(ModeloAuditoria.PERIODICIDADE_CHOICES)
    por_periodicidade = [
        {
            "periodicidade": item["modelo__periodicidade"],
            "periodicidade_label": periodicidade_map.get(item["modelo__periodicidade"], item["modelo__periodicidade"]),
            "total": item["total"],
        }
        for item in por_periodicidade_raw
    ]

    chart_modelo_labels = [item["modelo__nome"] for item in por_modelo]
    chart_modelo_values = [item["total"] for item in por_modelo]
    chart_periodicidade_labels = [item["periodicidade_label"] for item in por_periodicidade]
    chart_periodicidade_values = [item["total"] for item in por_periodicidade]
    
    # Lista de todos os modelos para o filtro
    todos_modelos = ModeloAuditoria.objects.filter(ativo=True).order_by("nome")
    modelo_selecionado = None
    if modelo_id:
        modelo_selecionado = ModeloAuditoria.objects.filter(pk=modelo_id).first()

    context = {
        "total_modelos": total_modelos,
        "total_registros": total_registros,
        "por_modelo": por_modelo,
        "por_periodicidade": por_periodicidade,
        "chart_modelo_labels": chart_modelo_labels,
        "chart_modelo_values": chart_modelo_values,
        "chart_periodicidade_labels": chart_periodicidade_labels,
        "chart_periodicidade_values": chart_periodicidade_values,
        "inicio": inicio,
        "fim": fim,
        "modelo_id": modelo_id,
        "todos_modelos": todos_modelos,
        "modelo_selecionado": modelo_selecionado,
    }
    return render(request, "auditoria/dashboard_auditoria.html", context)


@login_required
def registros_por_modelo(request, modelo_id):
    """Lista todos os registros preenchidos de um modelo específico"""
    modelo = get_object_or_404(ModeloAuditoria, pk=modelo_id)
    registros = RegistroAuditoria.objects.filter(modelo=modelo).select_related("avaliador").order_by("-data_auditoria")
    
    # Buscar perguntas do modelo
    perguntas = PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("ordem")
    
    # Estatísticas por pergunta
    estatisticas_perguntas = []
    
    # Dados separados por tipo de gráfico
    # Gráfico 1: Sim/Não (barras agrupadas)
    simnao_labels = []
    simnao_sim = []
    simnao_nao = []
    
    # Gráfico 2: Números (linhas - evolução temporal)
    # Vamos coletar dados por registro e pergunta para mostrar evolução
    numero_perguntas = []
    numero_datasets = []
    
    for pergunta in perguntas:
        respostas = RespostaAuditoria.objects.filter(pergunta=pergunta, registro__in=registros).select_related('registro')
        total_respostas = respostas.count()
        
        estatistica = {
            "pergunta": pergunta.pergunta,
            "tipo": pergunta.get_tipo_resposta_display(),
            "total_respostas": total_respostas,
        }
        
        if pergunta.tipo_resposta in ["SIM_NAO", "BOOLEANO"]:
            # Contar respostas Sim e Não
            sim_count = respostas.filter(valor__in=["True", "true", "Sim", "sim", "1"]).count()
            nao_count = respostas.filter(valor__in=["False", "false", "Não", "não", "Nao", "nao", "0"]).count()
            estatistica["sim"] = sim_count
            estatistica["nao"] = nao_count
            
            # Adicionar aos dados do gráfico de barras
            label = pergunta.pergunta[:30] + "..." if len(pergunta.pergunta) > 30 else pergunta.pergunta
            simnao_labels.append(label)
            simnao_sim.append(sim_count)
            simnao_nao.append(nao_count)
            
        elif pergunta.tipo_resposta in ["NUMERO", "DECIMAL"]:
            # Coletar valores para gráfico de linhas (evolução)
            valores_resposta = []
            datas_resposta = []
            
            for resposta in respostas.order_by('registro__data_auditoria'):
                try:
                    valor = float(resposta.valor) if resposta.valor else None
                    if valor is not None:
                        valores_resposta.append(valor)
                        datas_resposta.append(resposta.registro.data_auditoria.strftime('%d/%m/%Y'))
                except (ValueError, TypeError):
                    pass
            
            if valores_resposta:
                media = sum(valores_resposta) / len(valores_resposta)
                estatistica["media"] = round(media, 2)
                estatistica["valores"] = valores_resposta
                
                # Adicionar dataset para este pergunta no gráfico de linhas
                label = pergunta.pergunta[:30] + "..." if len(pergunta.pergunta) > 30 else pergunta.pergunta
                numero_perguntas.append({
                    "label": label,
                    "valores": valores_resposta,
                    "datas": datas_resposta
                })
                
        estatisticas_perguntas.append(estatistica)
    
    # Preparar dados para gráfico de linhas (números)
    # Agrupar por data para mostrar evolução temporal
    numero_chart_labels = []
    numero_chart_datasets = []
    
    if numero_perguntas:
        # Coletar todas as datas únicas (ordenadas)
        todas_datas = set()
        for perg in numero_perguntas:
            todas_datas.update(perg['datas'])
        numero_chart_labels = sorted(list(todas_datas), key=lambda x: tuple(reversed(x.split('/'))))
        
        # Criar um dataset para cada pergunta
        cores = [
            {"bg": "rgba(255, 99, 132, 0.2)", "border": "rgba(255, 99, 132, 1)"},
            {"bg": "rgba(54, 162, 235, 0.2)", "border": "rgba(54, 162, 235, 1)"},
            {"bg": "rgba(255, 206, 86, 0.2)", "border": "rgba(255, 206, 86, 1)"},
            {"bg": "rgba(75, 192, 192, 0.2)", "border": "rgba(75, 192, 192, 1)"},
            {"bg": "rgba(153, 102, 255, 0.2)", "border": "rgba(153, 102, 255, 1)"},
        ]
        
        for idx, perg in enumerate(numero_perguntas):
            # Mapear valores para as datas correspondentes
            data_valor_map = dict(zip(perg['datas'], perg['valores']))
            valores_ordenados = [data_valor_map.get(data, None) for data in numero_chart_labels]
            
            cor = cores[idx % len(cores)]
            numero_chart_datasets.append({
                "label": perg['label'],
                "data": valores_ordenados,
                "borderColor": cor['border'],
                "backgroundColor": cor['bg'],
                "tension": 0.3,
                "fill": False
            })
    
    context = {
        "modelo": modelo,
        "registros": registros,
        "perguntas": perguntas,
        "estatisticas_perguntas": estatisticas_perguntas,
        # Gráfico Sim/Não
        "simnao_labels": json.dumps(simnao_labels),
        "simnao_sim": json.dumps(simnao_sim),
        "simnao_nao": json.dumps(simnao_nao),
        # Gráfico Números
        "numero_labels": json.dumps(numero_chart_labels),
        "numero_datasets": json.dumps(numero_chart_datasets),
    }
    return render(request, "auditoria/registros_por_modelo.html", context)


@login_required
def exportar_respostas_excel(request, modelo_id):
    """Exporta em Excel (.xlsx) as respostas registradas de um modelo específico."""
    from openpyxl import Workbook

    modelo = get_object_or_404(ModeloAuditoria, pk=modelo_id)

    perguntas = list(
        PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("ordem", "id")
    )
    registros = (
        RegistroAuditoria.objects.filter(modelo=modelo)
        .select_related("avaliador")
        .prefetch_related("respostas__pergunta")
        .order_by("-data_auditoria", "-id")
    )

    def _normalize_sim_nao(value: str) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if raw in {"True", "true", "Sim", "sim", "1", "SIM"}:
            return "Sim"
        if raw in {"False", "false", "Não", "não", "Nao", "nao", "0", "NAO", "NÃO"}:
            return "Não"
        return raw

    # Mapear respostas por registro/pergunta
    respostas_por_registro: dict[int, dict[int, str]] = {}
    for registro in registros:
        respostas_por_registro[registro.id] = {}
        for resposta in getattr(registro, "respostas").all():
            respostas_por_registro[registro.id][resposta.pergunta_id] = resposta.valor

    wb = Workbook()
    ws = wb.active
    ws.title = "Respostas"

    headers = [
        "ID",
        "Data Auditoria",
        "Período Início",
        "Período Fim",
        "Avaliador",
        "Observações",
    ]
    headers.extend([p.pergunta for p in perguntas])
    ws.append(headers)

    for registro in registros:
        avaliador = ""
        if registro.avaliador_id:
            avaliador = registro.avaliador.get_full_name() or registro.avaliador.username

        row = [
            registro.id,
            registro.data_auditoria.strftime("%d/%m/%Y") if registro.data_auditoria else "",
            registro.periodo_inicio.strftime("%d/%m/%Y") if registro.periodo_inicio else "",
            registro.periodo_fim.strftime("%d/%m/%Y") if registro.periodo_fim else "",
            avaliador,
            registro.observacoes or "",
        ]

        respostas_dict = respostas_por_registro.get(registro.id, {})
        for pergunta in perguntas:
            valor = respostas_dict.get(pergunta.id, "")
            if pergunta.tipo_resposta in ["SIM_NAO", "BOOLEANO"]:
                row.append(_normalize_sim_nao(valor))
            else:
                row.append(valor or "")

        ws.append(row)

    # Gerar arquivo em memória
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    safe_name = "".join(c for c in (modelo.nome or "modelo") if c.isalnum() or c in {" ", "-", "_"}).strip()
    if not safe_name:
        safe_name = f"modelo_{modelo.id}"
    filename = f"respostas_{safe_name}.xlsx"

    response = HttpResponse(
        stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
