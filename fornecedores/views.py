from django.views.decorators.http import require_GET
# API para respostas de avaliação (edição)
@require_GET
def api_respostas_avaliacao(request, avaliacao_id):
    from .models import RespostaAvaliacao
    respostas = RespostaAvaliacao.objects.filter(avaliacao_id=avaliacao_id)
    data = {}
    for r in respostas:
        data[r.pergunta_id] = {"resposta": r.resposta, "observacao": r.observacao}
    return JsonResponse({"respostas": data})
def avaliacao_edit(request, fornecedor_id, avaliacao_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    avaliacao = get_object_or_404(fornecedor.avaliacoes, pk=avaliacao_id)
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST, instance=avaliacao)
        tipo_nota = form.data.get("tipo_nota")
        perguntas = PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True)
        if tipo_nota:
            perguntas = perguntas.filter(models.Q(produto_servico=tipo_nota) | models.Q(produto_servico="AMBOS"))
        perguntas = perguntas.order_by("ordem")
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.fornecedor = fornecedor
            avaliacao.tipo = "MONITORAMENTO"
            avaliacao.avaliador = request.user
            avaliacao.save()
            # Remove respostas antigas e salva novas
            avaliacao.respostas.all().delete()
            total_ocorrencias = 0
            for p in perguntas:
                resposta_val = request.POST.get(f"resposta_{p.id}")
                obs_val = request.POST.get(f"observacao_{p.id}", "")
                resposta_bool = True if resposta_val == "on" else False
                if not resposta_bool:
                    total_ocorrencias += 1
                RespostaAvaliacao.objects.create(
                    avaliacao=avaliacao,
                    pergunta=p,
                    resposta=resposta_bool,
                    observacao=obs_val
                )
            avaliacao.pontuacao_ano = max(0, 100 - total_ocorrencias * 0.5)
            if avaliacao.pontuacao_ano >= 75:
                avaliacao.resultado = "Excelente"
            elif avaliacao.pontuacao_ano >= 50:
                avaliacao.resultado = "Bom"
            else:
                avaliacao.resultado = "Ruim"
            avaliacao.save()
            messages.success(request, "Avaliação atualizada com sucesso!")
            return redirect(reverse("fornecedores:avaliacao_list", args=[fornecedor.pk]))
    else:
        form = AvaliacaoFornecedorForm(instance=avaliacao)
        tipo_nota = form.initial.get("tipo_nota") or avaliacao.tipo_nota or None
        perguntas = PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True)
        if tipo_nota:
            perguntas = perguntas.filter(models.Q(produto_servico=tipo_nota) | models.Q(produto_servico="AMBOS"))
        perguntas = perguntas.order_by("ordem")
        respostas = [RespostaAvaliacaoForm(prefix=str(p.id), initial={"pergunta": p}) for p in perguntas]
    return render(request, "fornecedores/avaliacao_form.html", {"form": form, "respostas": respostas, "fornecedor": fornecedor, "edicao": True, "avaliacao": avaliacao})
from django.http import JsonResponse

def perguntas_filtradas(request):
    tipo = request.GET.get("tipo")
    tipo_nota = request.GET.get("tipo_nota")
    perguntas = PerguntaAvaliacao.objects.filter(tipo=tipo, ativo=True)
    if tipo == "MONITORAMENTO" and tipo_nota:
        perguntas = perguntas.filter(models.Q(produto_servico=tipo_nota) | models.Q(produto_servico="AMBOS"))
    perguntas = perguntas.order_by("ordem")
    data = [
        {
            "id": p.id,
            "texto": p.texto,
            "produto_servico": p.get_produto_servico_display() if p.produto_servico else "",
        }
        for p in perguntas
    ]
    return JsonResponse({"perguntas": data})
def pergunta_edit(request, pk):
    pergunta = get_object_or_404(PerguntaAvaliacao, pk=pk)
    if request.method == "POST":
        form = PerguntaAvaliacaoForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            return redirect("fornecedores:pergunta_list")
    else:
        form = PerguntaAvaliacaoForm(instance=pergunta)
    return render(request, "fornecedores/pergunta_form.html", {"form": form, "pergunta": pergunta})

def pergunta_delete(request, pk):
    pergunta = get_object_or_404(PerguntaAvaliacao, pk=pk)
    if request.method == "POST":
        pergunta.delete()
        return redirect("fornecedores:pergunta_list")
    return render(request, "fornecedores/pergunta_confirm_delete.html", {"pergunta": pergunta})
from .forms_pergunta import PerguntaAvaliacaoForm
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import Fornecedor, DocumentoFornecedor, AvaliacaoFornecedor, PerguntaAvaliacao, RespostaAvaliacao, RespostaMatrizAvaliacao
from django.db import models
from .forms import FornecedorForm
from .forms_documento import DocumentoFornecedorForm
from .forms_avaliacao import AvaliacaoFornecedorForm, RespostaAvaliacaoForm
from django.contrib import messages
import pandas as pd
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone

def fornecedor_list(request):
    fornecedores = Fornecedor.objects.all()
    tipo = request.GET.get("tipo")
    uf = request.GET.get("uf")
    ativo = request.GET.get("ativo")
    q = request.GET.get("q")
    if tipo:
        fornecedores = fornecedores.filter(tipo=tipo)
    if uf:
        fornecedores = fornecedores.filter(uf=uf)
    if ativo in ["True", "False"]:
        fornecedores = fornecedores.filter(ativo=(ativo == "True"))
    if q:
        fornecedores = fornecedores.filter(
            Q(empresa__icontains=q) |
            Q(nome_fantasia__icontains=q) |
            Q(cnpj__icontains=q)
        )
    ufs = Fornecedor.objects.values_list("uf", flat=True).distinct().order_by("uf")
    return render(request, "fornecedores/fornecedor_list.html", {"fornecedores": fornecedores, "ufs": ufs})

def fornecedor_detail(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    
    # Perguntas de Avaliação (SELECAO)
    perguntas_avaliacao = PerguntaAvaliacao.objects.filter(tipo="SELECAO", ativo=True).order_by("ordem")
    
    # Respostas de Avaliação (SELECAO) - última avaliação
    ultima_avaliacao_selecao = None
    respostas_avaliacao = []
    percentual_avaliacao = 0
    
    if perguntas_avaliacao.exists():
        # Busca a última avaliação do tipo SELECAO
        ultima_avaliacao_selecao = AvaliacaoFornecedor.objects.filter(
            fornecedor=fornecedor,
            tipo="SELECAO"
        ).order_by("-data").first()
        
        if ultima_avaliacao_selecao:
            # Busca todas as respostas dessa avaliação
            respostas_avaliacao = RespostaAvaliacao.objects.filter(
                avaliacao=ultima_avaliacao_selecao
            ).order_by("pergunta__ordem")
            
            # Calcula percentual: (respostas SIM / total perguntas) * 100
            total_perguntas = perguntas_avaliacao.count()
            respostas_sim = respostas_avaliacao.filter(resposta=True).count()
            percentual_avaliacao = (respostas_sim / total_perguntas * 100) if total_perguntas > 0 else 0
    
    # Perguntas de Reavaliação (REAVALIACAO)
    perguntas_reavaliacao = PerguntaAvaliacao.objects.filter(tipo="REAVALIACAO", ativo=True).order_by("ordem")
    
    # Respostas de Reavaliação - última reavaliação
    ultima_reavaliacao = None
    respostas_reavaliacao = []
    percentual_reavaliacao = 0
    
    if perguntas_reavaliacao.exists():
        # Busca a última reavaliação do tipo REAVALIACAO
        ultima_reavaliacao = AvaliacaoFornecedor.objects.filter(
            fornecedor=fornecedor,
            tipo="REAVALIACAO"
        ).order_by("-data").first()
        
        if ultima_reavaliacao:
            # Busca todas as respostas dessa reavaliação
            respostas_reavaliacao = RespostaAvaliacao.objects.filter(
                avaliacao=ultima_reavaliacao
            ).order_by("pergunta__ordem")
            
            # Calcula percentual: (respostas SIM / total perguntas) * 100
            total_perguntas = perguntas_reavaliacao.count()
            respostas_sim = respostas_reavaliacao.filter(resposta=True).count()
            percentual_reavaliacao = (respostas_sim / total_perguntas * 100) if total_perguntas > 0 else 0
    
    # Perguntas de Monitoramento
    perguntas = PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True).order_by("ordem")
    grupos = {"PRODUTO": [], "SERVICO": [], "AMBOS": []}
    for pergunta in perguntas:
        total = RespostaAvaliacao.objects.filter(
            pergunta=pergunta,
            resposta=False,
            avaliacao__fornecedor=fornecedor
        ).count()
        item = {
            "pergunta": pergunta,
            "ocorrencias": total,
            "saldo": -0.5 * total
        }
        if pergunta.produto_servico == "PRODUTO":
            grupos["PRODUTO"].append(item)
        elif pergunta.produto_servico == "SERVICO":
            grupos["SERVICO"].append(item)
        else:
            grupos["AMBOS"].append(item)
    somas = {k: sum(i["saldo"] for i in v) for k, v in grupos.items()}
    saldo_total = somas["PRODUTO"] + somas["SERVICO"] + somas["AMBOS"]
    pontuacao_geral = 100 + saldo_total  # saldo_total é negativo
    return render(request, "fornecedores/fornecedor_detail.html", {
        "fornecedor": fornecedor,
        "perguntas_avaliacao": perguntas_avaliacao,
        "ultima_avaliacao_selecao": ultima_avaliacao_selecao,
        "respostas_avaliacao": respostas_avaliacao,
        "percentual_avaliacao": percentual_avaliacao,
        "perguntas_reavaliacao": perguntas_reavaliacao,
        "ultima_reavaliacao": ultima_reavaliacao,
        "respostas_reavaliacao": respostas_reavaliacao,
        "percentual_reavaliacao": percentual_reavaliacao,
        "monitoramento_produto": grupos["PRODUTO"],
        "monitoramento_servico": grupos["SERVICO"],
        "monitoramento_ambos": grupos["AMBOS"],
        "soma_produto": somas["PRODUTO"],
        "soma_servico": somas["SERVICO"],
        "soma_ambos": somas["AMBOS"],
        "saldo_total": saldo_total,
        "pontuacao_geral": pontuacao_geral
    })

def fornecedor_create(request):
    if request.method == "POST":
        form = FornecedorForm(request.POST)
        if form.is_valid():
            fornecedor = form.save()
            messages.success(request, "Fornecedor cadastrado com sucesso!")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    else:
        form = FornecedorForm()
    return render(request, "fornecedores/fornecedor_form.html", {"form": form, "fornecedor": None})

def fornecedor_update(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    if request.method == "POST":
        form = FornecedorForm(request.POST, instance=fornecedor)
        if form.is_valid():
            fornecedor = form.save()
            messages.success(request, "Fornecedor atualizado com sucesso!")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    else:
        form = FornecedorForm(instance=fornecedor)
    return render(request, "fornecedores/fornecedor_form.html", {"form": form, "fornecedor": fornecedor})

def pergunta_list(request):
    perguntas = PerguntaAvaliacao.objects.all().order_by("tipo", "ordem")
    return render(request, "fornecedores/pergunta_list.html", {"perguntas": perguntas})

def pergunta_create(request):
    if request.method == "POST":
        form = PerguntaAvaliacaoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("fornecedores:pergunta_list")
    else:
        form = PerguntaAvaliacaoForm()
    return render(request, "fornecedores/pergunta_form.html", {"form": form})
def documento_create(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    if request.method == "POST":
        form = DocumentoFornecedorForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.fornecedor = fornecedor
            doc.save()
            messages.success(request, "Documento cadastrado com sucesso!")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    else:
        form = DocumentoFornecedorForm()
    return render(request, "fornecedores/documento_form.html", {"form": form, "fornecedor": fornecedor})

def documento_delete(request, fornecedor_id, doc_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    doc = get_object_or_404(DocumentoFornecedor, pk=doc_id, fornecedor=fornecedor)
    if request.method == "POST":
        doc.delete()
        messages.success(request, "Documento removido com sucesso!")
        return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    return render(request, "fornecedores/documento_confirm_delete.html", {"documento": doc, "fornecedor": fornecedor})

def avaliacao_selecao_create(request, fornecedor_id):
    """Criar/editar avaliação de SELECAO (Avaliação Inicial)"""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    perguntas = PerguntaAvaliacao.objects.filter(tipo="SELECAO", ativo=True).order_by("ordem")
    
    # Busca última avaliação SELECAO
    ultima_avaliacao = AvaliacaoFornecedor.objects.filter(
        fornecedor=fornecedor,
        tipo="SELECAO"
    ).order_by("-data").first()
    
    if request.method == "POST":
        # Converte data do POST (string) para date object
        data_str = request.POST.get("data")
        try:
            from datetime import datetime
            data_submit = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else timezone.now().date()
        except (ValueError, TypeError):
            data_submit = timezone.now().date()
        
        if ultima_avaliacao and ultima_avaliacao.data == data_submit:
            # Atualizar avaliação existente
            avaliacao = ultima_avaliacao
            avaliacao.observacao = request.POST.get("observacao", "")
            avaliacao.save()
            
            # Deleta respostas antigas
            avaliacao.respostas.all().delete()
        else:
            # Cria nova avaliação SELECAO
            avaliacao = AvaliacaoFornecedor(
                fornecedor=fornecedor,
                data=data_submit,
                tipo="SELECAO",
                avaliador=request.user,
                observacao=request.POST.get("observacao", "")
            )
            avaliacao.save()
        
        # Salva as respostas
        total_sim = 0
        for p in perguntas:
            resposta_val = request.POST.get(f"resposta_{p.id}")
            resposta_bool = resposta_val == "on"
            if resposta_bool:
                total_sim += 1
            RespostaAvaliacao.objects.create(
                avaliacao=avaliacao,
                pergunta=p,
                resposta=resposta_bool,
                observacao=""
            )
        
        # Calcula pontuação percentual
        total_perguntas = perguntas.count()
        percentual = (total_sim / total_perguntas * 100) if total_perguntas > 0 else 0
        avaliacao.pontuacao_ano = percentual
        
        if percentual >= 80:
            avaliacao.resultado = "Excelente"
        elif percentual >= 60:
            avaliacao.resultado = "Bom"
        elif percentual >= 40:
            avaliacao.resultado = "Satisfatório"
        else:
            avaliacao.resultado = "Insatisfatório"
        
        avaliacao.save()
        messages.success(request, "Avaliação de Seleção registrada com sucesso!")
        return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    
    # GET - Montar lista de respostas para pré-preenchimento
    respostas_existentes = {}
    if ultima_avaliacao:
        for resposta in ultima_avaliacao.respostas.all():
            respostas_existentes[resposta.pergunta_id] = {
                'resposta': resposta.resposta,
                'observacao': resposta.observacao
            }
    
    # Preparar lista de perguntas com respostas
    perguntas_com_respostas = []
    for pergunta in perguntas:
        resp = respostas_existentes.get(pergunta.id, {'resposta': False, 'observacao': ''})
        perguntas_com_respostas.append({
            'pergunta': pergunta,
            'resposta_anterior': resp['resposta'],
            'observacao_anterior': resp['observacao']
        })
    
    return render(request, "fornecedores/avaliacao_selecao_form.html", {
        "fornecedor": fornecedor,
        "perguntas_com_respostas": perguntas_com_respostas,
        "ultima_avaliacao": ultima_avaliacao,
        "today": timezone.now().date(),
    })

def avaliacao_reavaliacao_create(request, fornecedor_id):
    """Criar/editar reavaliação (REAVALIACAO) - anualmente a partir de janeiro"""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    perguntas = PerguntaAvaliacao.objects.filter(tipo="REAVALIACAO", ativo=True).order_by("ordem")
    
    # Busca última reavaliação
    ultima_reavaliacao = AvaliacaoFornecedor.objects.filter(
        fornecedor=fornecedor,
        tipo="REAVALIACAO"
    ).order_by("-data").first()
    
    if request.method == "POST":
        # Converte data do POST (string) para date object
        data_str = request.POST.get("data")
        try:
            from datetime import datetime
            data_submit = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else timezone.now().date()
        except (ValueError, TypeError):
            data_submit = timezone.now().date()
        
        # Validar: reavaliação só pode ser feita a partir de janeiro
        # e apenas uma vez por ano (safra anual)
        if data_submit.month < 1:  # Impossível, mas segurança
            data_submit = timezone.now().date()
        
        # Validar se já existe uma reavaliação no mesmo ano
        reavaliacao_ano_atual = AvaliacaoFornecedor.objects.filter(
            fornecedor=fornecedor,
            tipo="REAVALIACAO",
            data__year=data_submit.year
        ).exclude(id=ultima_reavaliacao.id if ultima_reavaliacao else None).exists()
        
        if reavaliacao_ano_atual and not (ultima_reavaliacao and ultima_reavaliacao.data.year == data_submit.year and ultima_reavaliacao.data == data_submit):
            messages.error(request, "Já existe uma reavaliação registrada para este ano. A próxima reavaliação só poderá ser realizada a partir de janeiro do próximo ano.")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
        
        if ultima_reavaliacao and ultima_reavaliacao.data == data_submit:
            # Atualizar reavaliação existente (mesma data)
            avaliacao = ultima_reavaliacao
            avaliacao.observacao = request.POST.get("observacao", "")
            avaliacao.save()
            
            # Deleta respostas antigas
            avaliacao.respostas.all().delete()
        else:
            # Cria nova reavaliação
            avaliacao = AvaliacaoFornecedor(
                fornecedor=fornecedor,
                data=data_submit,
                tipo="REAVALIACAO",
                avaliador=request.user,
                observacao=request.POST.get("observacao", "")
            )
            avaliacao.save()
        
        # Salva as respostas
        total_sim = 0
        for p in perguntas:
            resposta_val = request.POST.get(f"resposta_{p.id}")
            resposta_bool = resposta_val == "on"
            if resposta_bool:
                total_sim += 1
            RespostaAvaliacao.objects.create(
                avaliacao=avaliacao,
                pergunta=p,
                resposta=resposta_bool,
                observacao=""
            )
        
        # Calcula pontuação percentual
        total_perguntas = perguntas.count()
        percentual = (total_sim / total_perguntas * 100) if total_perguntas > 0 else 0
        avaliacao.pontuacao_ano = percentual
        
        # Reavaliação: apenas Aprovado (≥60%) ou Reprovado (<60%)
        if percentual >= 60:
            avaliacao.resultado = "Aprovado"
        else:
            avaliacao.resultado = "Reprovado"
        
        avaliacao.save()
        messages.success(request, "Reavaliação registrada com sucesso!")
        return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    
    # GET - Montar lista de respostas para pré-preenchimento
    respostas_existentes = {}
    if ultima_reavaliacao:
        for resposta in ultima_reavaliacao.respostas.all():
            respostas_existentes[resposta.pergunta_id] = {
                'resposta': resposta.resposta,
                'observacao': resposta.observacao
            }
    
    # Preparar lista de perguntas com respostas
    perguntas_com_respostas = []
    for pergunta in perguntas:
        resp = respostas_existentes.get(pergunta.id, {'resposta': False, 'observacao': ''})
        perguntas_com_respostas.append({
            'pergunta': pergunta,
            'resposta_anterior': resp['resposta'],
            'observacao_anterior': resp['observacao']
        })
    
    return render(request, "fornecedores/avaliacao_reavaliacao_form.html", {
        "fornecedor": fornecedor,
        "perguntas_com_respostas": perguntas_com_respostas,
        "ultima_reavaliacao": ultima_reavaliacao,
        "today": timezone.now().date(),
    })

def avaliacao_create(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST)
        tipo_nota = form.data.get("tipo_nota")
        perguntas = PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True)
        if tipo_nota:
            perguntas = perguntas.filter(models.Q(produto_servico=tipo_nota) | models.Q(produto_servico="AMBOS"))
        perguntas = perguntas.order_by("ordem")
        if form.is_valid():
            # Se existe avaliação de hoje, atualiza ao invés de criar
            data_submit = form.cleaned_data.get("data") or timezone.now().date()
            
            ultima_avaliacao = AvaliacaoFornecedor.objects.filter(
                fornecedor=fornecedor,
                tipo="MONITORAMENTO",
                data=data_submit
            ).order_by("-id").first()
            
            if ultima_avaliacao:
                # Atualizar avaliação existente
                avaliacao = ultima_avaliacao
                avaliacao.save()
                
                # Deleta respostas antigas
                avaliacao.respostas.all().delete()
            else:
                # Cria nova avaliação
                avaliacao = form.save(commit=False)
                avaliacao.fornecedor = fornecedor
                avaliacao.tipo = "MONITORAMENTO"
                avaliacao.avaliador = request.user
                avaliacao.save()
            
            total_ocorrencias = 0
            for p in perguntas:
                resposta_val = request.POST.get(f"resposta_{p.id}")
                obs_val = request.POST.get(f"observacao_{p.id}", "")
                resposta_bool = True if resposta_val == "on" else False
                if not resposta_bool:
                    total_ocorrencias += 1
                RespostaAvaliacao.objects.create(
                    avaliacao=avaliacao,
                    pergunta=p,
                    resposta=resposta_bool,
                    observacao=obs_val
                )
            avaliacao.pontuacao_ano = max(0, 100 - total_ocorrencias * 0.5)
            if avaliacao.pontuacao_ano >= 75:
                avaliacao.resultado = "Excelente"
            elif avaliacao.pontuacao_ano >= 50:
                avaliacao.resultado = "Bom"
            else:
                avaliacao.resultado = "Ruim"
            avaliacao.save()
            messages.success(request, "Avaliação registrada com sucesso!")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    else:
        form = AvaliacaoFornecedorForm()
        tipo_nota = form.initial.get("tipo_nota") or None
        perguntas = PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True)
        if tipo_nota:
            perguntas = perguntas.filter(models.Q(produto_servico=tipo_nota) | models.Q(produto_servico="AMBOS"))
        perguntas = perguntas.order_by("ordem")
        respostas = [RespostaAvaliacaoForm(prefix=str(p.id), initial={"pergunta": p}) for p in perguntas]
    return render(request, "fornecedores/avaliacao_form.html", {"form": form, "respostas": respostas, "fornecedor": fornecedor})

def avaliacao_list(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    if request.method == "POST" and request.POST.get("delete_id"):
        delete_id = request.POST.get("delete_id")
        avaliacao = fornecedor.avaliacoes.filter(id=delete_id).first()
        if avaliacao:
            avaliacao.delete()
            messages.success(request, "Avaliação removida com sucesso!")
    avaliacoes = fornecedor.avaliacoes.all().order_by("-data")
    # Para cada avaliação, buscar perguntas respondidas como NÃO
    avaliacoes_info = []
    for av in avaliacoes:
        perguntas_nao = av.respostas.filter(resposta=False)
        avaliacoes_info.append({
            "obj": av,
            "perguntas_nao": perguntas_nao,
        })
    return render(request, "fornecedores/avaliacao_list.html", {"avaliacoes_info": avaliacoes_info, "fornecedor": fornecedor})

def reavaliacao_create(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST)
        perguntas = PerguntaAvaliacao.objects.filter(tipo="REAVALIACAO", ativo=True).order_by("ordem")
        respostas = [RespostaAvaliacaoForm(request.POST, prefix=str(p.id)) for p in perguntas]
        if form.is_valid() and all(rf.is_valid() for rf in respostas):
            avaliacao = form.save(commit=False)
            avaliacao.fornecedor = fornecedor
            avaliacao.avaliador = request.user
            avaliacao.tipo = "REAVALIACAO"
            avaliacao.save()
            total_sim = 0
            for rf in respostas:
                resposta = rf.save(commit=False)
                resposta.avaliacao = avaliacao
                resposta.save()
                if rf.cleaned_data["resposta"]:
                    total_sim += 1
            total_perguntas = len(respostas)
            percentual = (total_sim / total_perguntas) * 100 if total_perguntas else 0
            avaliacao.pontuacao_ano = percentual
            if percentual >= 60:
                avaliacao.resultado = "Aprovado"
            else:
                avaliacao.resultado = "Reprovado"
            avaliacao.save()
            messages.success(request, "Reavaliação registrada com sucesso!")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    else:
        form = AvaliacaoFornecedorForm(initial={"tipo": "REAVALIACAO"})
        perguntas = PerguntaAvaliacao.objects.filter(tipo="REAVALIACAO", ativo=True).order_by("ordem")
        respostas = [RespostaAvaliacaoForm(prefix=str(p.id), initial={"pergunta": p}) for p in perguntas]
    return render(request, "fornecedores/reavaliacao_form.html", {"form": form, "respostas": respostas, "fornecedor": fornecedor})

def reavaliacao_list(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    reavaliacoes = fornecedor.avaliacoes.filter(tipo="REAVALIACAO").order_by("-data")
    
    # Enriquecer dados de reavaliações com respostas
    reavaliacoes_detalhes = []
    for reavaliacao in reavaliacoes:
        respostas = RespostaAvaliacao.objects.filter(avaliacao=reavaliacao).order_by("pergunta__ordem")
        reavaliacoes_detalhes.append({
            'reavaliacao': reavaliacao,
            'respostas': respostas,
            'total_respostas': respostas.count(),
            'respostas_sim': respostas.filter(resposta=True).count(),
        })
    
    return render(request, "fornecedores/reavaliacao_list.html", {
        "reavaliacoes_detalhes": reavaliacoes_detalhes,
        "fornecedor": fornecedor,
        "total_reavaliacoes": len(reavaliacoes_detalhes),
        "today": timezone.now().date()
    })

def export_avaliacoes_excel(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    avaliacoes = fornecedor.avaliacoes.all().order_by("-data")
    data = []
    for av in avaliacoes:
        respostas = av.respostas.all()
        respostas_dict = {r.pergunta.texto: ("Sim" if r.resposta else "Não") for r in respostas}
        row = {
            "Data": av.data,
            "Tipo": av.get_tipo_display(),
            "Avaliador": str(av.avaliador),
            "Pontuação": av.pontuacao_ano,
            "Resultado": av.resultado,
            **respostas_dict
        }
        data.append(row)
    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=avaliacoes_{fornecedor.empresa}.xlsx'
    df.to_excel(response, index=False)
    return response

def avaliacao_matriz_create(request, fornecedor_id):
    """Criar/editar avaliação tipo matriz com requisitos A, B, C, D para Produto e Serviço"""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    
    # Busca última avaliação de matriz (MONITORAMENTO)
    ultima_matriz = AvaliacaoFornecedor.objects.filter(
        fornecedor=fornecedor,
        tipo="MONITORAMENTO"
    ).order_by("-data").first()
    
    if request.method == "POST":
        # Cria nova avaliação de matriz
        avaliacao = AvaliacaoFornecedor(
            fornecedor=fornecedor,
            data=request.POST.get("data") or timezone.now().date(),
            tipo="MONITORAMENTO",
            avaliador=request.user,
            observacao=request.POST.get("observacao", "")
        )
        avaliacao.save()
        
        # Processa Produtos
        for requisito in ["A", "B", "C", "D"]:
            respondido = request.POST.get(f"matriz_PRODUTO_{requisito}") == "on"
            RespostaMatrizAvaliacao.objects.create(
                avaliacao=avaliacao,
                tipo="PRODUTO",
                nome_item="Produto",  # Genérico para produto
                requisito=requisito,
                respondido=respondido
            )
        
        # Processa Serviços
        for requisito in ["A", "B", "C", "D"]:
            respondido = request.POST.get(f"matriz_SERVICO_{requisito}") == "on"
            RespostaMatrizAvaliacao.objects.create(
                avaliacao=avaliacao,
                tipo="SERVICO",
                nome_item="Serviço",  # Genérico para serviço
                requisito=requisito,
                respondido=respondido
            )
        
        # Processa produtos/serviços listados (armazena na observação ou como respostas separadas)
        produtos = [p.strip() for p in request.POST.get("produtos", "").split("\n") if p.strip()]
        servicos = [s.strip() for s in request.POST.get("servicos", "").split("\n") if s.strip()]
        
        # Adiciona listagem de produtos e serviços na observação
        detalhes = []
        if produtos:
            detalhes.append("PRODUTOS:\n- " + "\n- ".join(produtos))
        if servicos:
            detalhes.append("SERVIÇOS:\n- " + "\n- ".join(servicos))
        
        if detalhes:
            avaliacao.observacao = (avaliacao.observacao + "\n\n" if avaliacao.observacao else "") + "\n\n".join(detalhes)
            avaliacao.save()
        
        messages.success(request, "Avaliação de matriz registrada com sucesso!")
        return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    
    # GET - Montar dados anteriores para pré-preenchimento
    produtos_anteriores = ""
    servicos_anteriores = ""
    respostas_anteriores = {}
    
    if ultima_matriz:
        # Extrai produtos e serviços da observação
        obs = ultima_matriz.observacao or ""
        if "PRODUTOS:" in obs:
            produtos_section = obs.split("PRODUTOS:")[1].split("SERVIÇOS:")[0] if "SERVIÇOS:" in obs else obs.split("PRODUTOS:")[1]
            produtos_anteriores = "\n".join([line.strip().lstrip("- ") for line in produtos_section.strip().split("\n") if line.strip()])
        if "SERVIÇOS:" in obs:
            servicos_section = obs.split("SERVIÇOS:")[1]
            servicos_anteriores = "\n".join([line.strip().lstrip("- ") for line in servicos_section.strip().split("\n") if line.strip()])
        
        # Busca respostas anteriores
        for resposta in ultima_matriz.respostas_matriz.all():
            key = f"{resposta.tipo}_{resposta.requisito}"
            respostas_anteriores[key] = resposta.respondido
    
    return render(request, "fornecedores/avaliacao_matriz_form.html", {
        "fornecedor": fornecedor,
        "ultima_matriz": ultima_matriz,
        "produtos_anteriores": produtos_anteriores,
        "servicos_anteriores": servicos_anteriores,
        "respostas_anteriores": respostas_anteriores,
    })

@login_required
def reavaliacao_delete(request, fornecedor_id):
    """
    Deleta a última reavaliação de um fornecedor.
    Sempre delete a mais recente para manter consistência.
    """
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    
    # Pega a última reavaliação
    ultima_reavaliacao = fornecedor.avaliacoes.filter(
        tipo="REAVALIACAO"
    ).order_by('-data').first()
    
    if not ultima_reavaliacao:
        messages.error(request, "Nenhuma reavaliação encontrada para deletar.")
        return redirect('fornecedores:reavaliacao_list', fornecedor_id=fornecedor_id)
    
    if request.method == 'POST':
        # Deleta todas as respostas da reavaliação
        ultima_reavaliacao.respostas.all().delete()
        
        # Deleta a reavaliação
        reavaliacao_data = ultima_reavaliacao.data
        ultima_reavaliacao.delete()
        
        messages.success(
            request, 
            f"Reavaliação de {reavaliacao_data.strftime('%d/%m/%Y')} deletada com sucesso."
        )
        return redirect('fornecedores:reavaliacao_list', fornecedor_id=fornecedor_id)
    
    # GET - mostra confirmação
    respostas = ultima_reavaliacao.respostas.all()
    
    return render(request, "fornecedores/reavaliacao_delete_confirm.html", {
        "fornecedor": fornecedor,
        "reavaliacao": ultima_reavaliacao,
        "total_respostas": respostas.count(),
    })
