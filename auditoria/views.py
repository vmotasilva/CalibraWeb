from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
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
    chart_labels = []
    chart_datasets = []
    
    # Preparar dados para cada tipo de resposta
    sim_data = []
    nao_data = []
    escala_data = []
    texto_data = []
    
    for pergunta in perguntas:
        respostas = RespostaAuditoria.objects.filter(pergunta=pergunta, registro__in=registros)
        total_respostas = respostas.count()
        
        # Label da pergunta (truncado)
        label = pergunta.pergunta[:40] + "..." if len(pergunta.pergunta) > 40 else pergunta.pergunta
        chart_labels.append(label)
        
        estatistica = {
            "pergunta": pergunta.pergunta,
            "tipo": pergunta.get_tipo_resposta_display(),
            "total_respostas": total_respostas,
        }
        
        if pergunta.tipo_resposta == "SIM_NAO":
            sim_count = respostas.filter(resposta_sim_nao=True).count()
            nao_count = respostas.filter(resposta_sim_nao=False).count()
            estatistica["sim"] = sim_count
            estatistica["nao"] = nao_count
            sim_data.append(sim_count)
            nao_data.append(nao_count)
            escala_data.append(None)
            texto_data.append(None)
            
        elif pergunta.tipo_resposta == "ESCALA_1_5":
            # Calcular média
            escalas = respostas.exclude(resposta_escala__isnull=True)
            if escalas.exists():
                from django.db.models import Avg
                media = escalas.aggregate(media=Avg("resposta_escala"))["media"]
                if media:
                    media_arredondada = round(media, 2)
                    estatistica["media_escala"] = media_arredondada
                    escala_data.append(media_arredondada)
                else:
                    escala_data.append(None)
            else:
                escala_data.append(None)
            sim_data.append(None)
            nao_data.append(None)
            texto_data.append(None)
            
        else:
            # Outros tipos (texto, data, etc)
            sim_data.append(None)
            nao_data.append(None)
            escala_data.append(None)
            texto_data.append(total_respostas if total_respostas > 0 else None)
                
        estatisticas_perguntas.append(estatistica)
    
    # Preparar datasets apenas com os que têm dados
    chart_datasets = []
    if any(x is not None for x in sim_data):
        chart_datasets.append({
            "label": "Sim",
            "data": sim_data,
            "backgroundColor": "rgba(40, 167, 69, 0.8)",
            "borderColor": "rgba(40, 167, 69, 1)",
        })
    if any(x is not None for x in nao_data):
        chart_datasets.append({
            "label": "Não",
            "data": nao_data,
            "backgroundColor": "rgba(220, 53, 69, 0.8)",
            "borderColor": "rgba(220, 53, 69, 1)",
        })
    if any(x is not None for x in escala_data):
        chart_datasets.append({
            "label": "Média (Escala 1-5)",
            "data": escala_data,
            "backgroundColor": "rgba(0, 123, 255, 0.8)",
            "borderColor": "rgba(0, 123, 255, 1)",
        })
    if any(x is not None for x in texto_data):
        chart_datasets.append({
            "label": "Respostas",
            "data": texto_data,
            "backgroundColor": "rgba(108, 117, 125, 0.8)",
            "borderColor": "rgba(108, 117, 125, 1)",
        })
    
    context = {
        "modelo": modelo,
        "registros": registros,
        "perguntas": perguntas,
        "estatisticas_perguntas": estatisticas_perguntas,
        "chart_labels": json.dumps(chart_labels),
        "chart_datasets": json.dumps(chart_datasets),
    }
    return render(request, "auditoria/registros_por_modelo.html", context)
