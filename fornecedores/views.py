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
from .models import Fornecedor, DocumentoFornecedor, AvaliacaoFornecedor, PerguntaAvaliacao, RespostaAvaliacao
from django.db import models
from .forms import FornecedorForm
from .forms_documento import DocumentoFornecedorForm
from .forms_avaliacao import AvaliacaoFornecedorForm, RespostaAvaliacaoForm
from django.contrib import messages
import pandas as pd
from django.http import HttpResponse
from django.db.models import Q

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
    
    # Perguntas de Avaliação agrupadas por tipo
    perguntas_por_tipo = {
        "SELECAO": {
            "nome": "Avaliação",
            "subgrupos": {"Requisitos": []},
            "perguntas": []
        },
        "REAVALIACAO": {
            "nome": "Reavaliação",
            "subgrupos": {"Critérios": []},
            "perguntas": []
        },
        "MONITORAMENTO": {
            "nome": "Monitoramento",
            "subgrupos": {"PRODUTO": [], "SERVICO": [], "AMBOS": []},
            "perguntas": []
        }
    }
    
    # Busca todas as perguntas ativas
    todas_perguntas = PerguntaAvaliacao.objects.filter(ativo=True).order_by("tipo", "ordem")
    
    for pergunta in todas_perguntas:
        if pergunta.tipo == "SELECAO":
            perguntas_por_tipo["SELECAO"]["perguntas"].append(pergunta)
        elif pergunta.tipo == "REAVALIACAO":
            perguntas_por_tipo["REAVALIACAO"]["perguntas"].append(pergunta)
        elif pergunta.tipo == "MONITORAMENTO":
            if pergunta.produto_servico == "PRODUTO":
                perguntas_por_tipo["MONITORAMENTO"]["subgrupos"]["PRODUTO"].append(pergunta)
            elif pergunta.produto_servico == "SERVICO":
                perguntas_por_tipo["MONITORAMENTO"]["subgrupos"]["SERVICO"].append(pergunta)
            elif pergunta.produto_servico == "AMBOS":
                perguntas_por_tipo["MONITORAMENTO"]["subgrupos"]["AMBOS"].append(pergunta)
    
    # Perguntas de Monitoramento (para cálculo de pontuação)
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
        "perguntas_por_tipo": perguntas_por_tipo,
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
    return render(request, "fornecedores/reavaliacao_list.html", {"reavaliacoes": reavaliacoes, "fornecedor": fornecedor})

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
