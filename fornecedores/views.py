from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from shared import planilha as pd
from shared.permissions import has_view_access

from . import services
from .forms import FornecedorForm
from .forms_avaliacao import AvaliacaoFornecedorForm
from .forms_documento import DocumentoFornecedorForm
from .forms_pergunta import PerguntaAvaliacaoForm
from .models import (
    AvaliacaoFornecedor,
    DocumentoFornecedor,
    Fornecedor,
    PerguntaAvaliacao,
    RespostaAvaliacao,
    RespostaMatrizAvaliacao,
)

ITENS_POR_PAGINA = 25
DIAS_ALERTA_VALIDADE = 30


# ----------------------------------------------------------------------------- helpers
def _parse_data(valor):
    """'YYYY-MM-DD' -> date, ou None se vazio/inválido."""
    try:
        return datetime.strptime((valor or "").strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _data_do_post(request):
    """Lê e valida a data do POST. Retorna (data, mensagem_de_erro)."""
    data = _parse_data(request.POST.get("data"))
    if data is None:
        return None, "Informe uma data válida."
    if data > timezone.localdate():
        return None, "A data da avaliação não pode ser futura."
    return data, None


def _perguntas_monitoramento(tipo_nota=None):
    perguntas = PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True)
    if tipo_nota:
        perguntas = perguntas.filter(Q(produto_servico=tipo_nota) | Q(produto_servico="AMBOS"))
    return perguntas.order_by("ordem", "id")


def _salvar_respostas(avaliacao, perguntas, post, com_observacao=False):
    """Substitui as respostas da avaliação pelas do POST. Retorna (total_sim, total_nao)."""
    avaliacao.respostas.all().delete()
    novas, sim = [], 0
    for p in perguntas:
        marcada = post.get(f"resposta_{p.id}") == "on"
        sim += marcada
        novas.append(RespostaAvaliacao(
            avaliacao=avaliacao,
            pergunta=p,
            resposta=marcada,
            observacao=post.get(f"observacao_{p.id}", "").strip() if com_observacao else "",
        ))
    RespostaAvaliacao.objects.bulk_create(novas)
    return sim, len(novas) - sim


def _respostas_existentes(avaliacao):
    if not avaliacao:
        return {}
    return {r.pergunta_id: r for r in avaliacao.respostas.all()}


def _perguntas_com_respostas(perguntas, avaliacao):
    existentes = _respostas_existentes(avaliacao)
    itens = []
    for pergunta in perguntas:
        r = existentes.get(pergunta.id)
        itens.append({
            "pergunta": pergunta,
            "resposta_anterior": bool(r and r.resposta),
            "observacao_anterior": r.observacao if r else "",
        })
    return itens


def _extrair_lista(obs, titulo, proximo):
    if titulo not in obs:
        return ""
    trecho = obs.split(titulo, 1)[1]
    if proximo in trecho:
        trecho = trecho.split(proximo, 1)[0]
    return "\n".join(linha.strip().lstrip("- ").strip() for linha in trecho.strip().split("\n") if linha.strip())


def _ultima_matriz(fornecedor):
    return (
        AvaliacaoFornecedor.objects.filter(fornecedor=fornecedor, tipo="MONITORAMENTO", respostas_matriz__isnull=False)
        .distinct()
        .order_by("-data", "-id")
        .first()
    )


def _dados_matriz(avaliacao):
    """(produtos, servicos, {'PRODUTO_A': bool, ...}) de uma avaliação de matriz."""
    if not avaliacao:
        return "", "", {}
    obs = avaliacao.observacao or ""
    produtos = _extrair_lista(obs, "PRODUTOS:", "SERVIÇOS:")
    servicos = _extrair_lista(obs, "SERVIÇOS:", "\0")
    respostas = {f"{r.tipo}_{r.requisito}": r.respondido for r in avaliacao.respostas_matriz.all()}
    return produtos, servicos, respostas


def _pode(request, view_name):
    return has_view_access(request.user, view_name)


# ----------------------------------------------------------------------------- fornecedores
@login_required
def fornecedor_list(request):
    fornecedores = Fornecedor.objects.all()
    tipo = request.GET.get("tipo")
    uf = request.GET.get("uf")
    ativo = request.GET.get("ativo")
    q = (request.GET.get("q") or "").strip()
    if tipo in dict(Fornecedor.TIPO_CHOICES):
        fornecedores = fornecedores.filter(tipo=tipo)
    if uf:
        fornecedores = fornecedores.filter(uf=uf)
    if ativo in ["True", "False"]:
        fornecedores = fornecedores.filter(ativo=(ativo == "True"))
    if q:
        fornecedores = fornecedores.filter(
            Q(empresa__icontains=q) | Q(nome_fantasia__icontains=q) | Q(cnpj__icontains=q)
        )
    fornecedores = fornecedores.order_by("empresa", "id")

    page_obj = Paginator(fornecedores, ITENS_POR_PAGINA).get_page(request.GET.get("page"))
    pagina = list(page_obj.object_list)
    ids = [f.pk for f in pagina]

    # Última avaliação de seleção / reavaliação de cada fornecedor da página (2 consultas, sem N+1).
    ultimas = {"SELECAO": {}, "REAVALIACAO": {}}
    registros = (
        AvaliacaoFornecedor.objects.filter(fornecedor_id__in=ids, tipo__in=ultimas.keys())
        .order_by("fornecedor_id", "-data", "-id")
    )
    for av in registros:
        ultimas[av.tipo].setdefault(av.fornecedor_id, av)
    monitoramento = services.pontuacoes_monitoramento_por_fornecedor(timezone.localdate().year)

    for f in pagina:
        sel, rea = ultimas["SELECAO"].get(f.pk), ultimas["REAVALIACAO"].get(f.pk)
        f.pontuacao_selecao = sel.pontuacao_ano if sel else None
        f.resultado_selecao = sel.resultado if sel else ""
        f.pontuacao_monitoramento = monitoramento.get(f.pk)
        f.resultado_monitoramento = (
            services.classificar_monitoramento(f.pontuacao_monitoramento) if f.pk in monitoramento else ""
        )
        f.pontuacao_reavaliacao = rea.pontuacao_ano if rea else None
        f.resultado_reavaliacao = rea.resultado if rea else ""

    filtros = request.GET.copy()
    filtros.pop("page", None)
    ufs = Fornecedor.objects.exclude(uf="").values_list("uf", flat=True).distinct().order_by("uf")
    return render(request, "fornecedores/fornecedor_list.html", {
        "fornecedores": pagina,
        "page_obj": page_obj,
        "querystring": filtros.urlencode(),
        "ufs": ufs,
        "ano_monitoramento": timezone.localdate().year,
    })


@login_required
def fornecedor_detail(request, pk):
    fornecedor = get_object_or_404(Fornecedor, pk=pk)
    hoje = timezone.localdate()
    ano = hoje.year

    # Documentos (com alerta de validade)
    limite = hoje + timedelta(days=DIAS_ALERTA_VALIDADE)
    documentos = list(fornecedor.documentos.select_related("categoria").order_by("categoria__nome", "id"))
    for doc in documentos:
        doc.vencido = bool(doc.data_validade and doc.data_validade < hoje)
        doc.a_vencer = bool(doc.data_validade and hoje <= doc.data_validade <= limite)

    # Avaliação (SELECAO)
    perguntas_avaliacao = PerguntaAvaliacao.objects.filter(tipo="SELECAO", ativo=True).order_by("ordem", "id")
    ultima_avaliacao_selecao = (
        AvaliacaoFornecedor.objects.filter(fornecedor=fornecedor, tipo="SELECAO").order_by("-data", "-id").first()
    )
    respostas_avaliacao = []
    percentual_avaliacao = None
    if ultima_avaliacao_selecao:
        respostas_avaliacao = ultima_avaliacao_selecao.respostas.select_related("pergunta").order_by("pergunta__ordem")
        percentual_avaliacao = ultima_avaliacao_selecao.pontuacao_ano

    # Reavaliação (REAVALIACAO)
    perguntas_reavaliacao = PerguntaAvaliacao.objects.filter(tipo="REAVALIACAO", ativo=True).order_by("ordem", "id")
    ultima_reavaliacao = (
        AvaliacaoFornecedor.objects.filter(fornecedor=fornecedor, tipo="REAVALIACAO").order_by("-data", "-id").first()
    )
    respostas_reavaliacao = []
    percentual_reavaliacao = None
    if ultima_reavaliacao:
        respostas_reavaliacao = ultima_reavaliacao.respostas.select_related("pergunta").order_by("pergunta__ordem")
        percentual_reavaliacao = ultima_reavaliacao.pontuacao_ano

    # Monitoramento: ocorrências (respostas NÃO) do ano corrente, em uma única consulta
    ocorrencias = services.ocorrencias_por_pergunta(fornecedor, ano)
    grupos = {"PRODUTO": [], "SERVICO": [], "AMBOS": []}
    for pergunta in PerguntaAvaliacao.objects.filter(tipo="MONITORAMENTO", ativo=True).order_by("ordem", "id"):
        total = ocorrencias.get(pergunta.id, 0)
        grupos.get(pergunta.produto_servico, grupos["AMBOS"]).append({
            "pergunta": pergunta,
            "ocorrencias": total,
            "saldo": -services.PENALIDADE_OCORRENCIA * total,
        })
    somas = {k: sum(i["saldo"] for i in v) for k, v in grupos.items()}
    saldo_total = sum(somas.values())
    pontuacao_geral = max(0.0, services.PONTUACAO_BASE_MONITORAMENTO + saldo_total)

    matriz = _ultima_matriz(fornecedor)
    matriz_produtos, matriz_servicos, matriz_respostas = _dados_matriz(matriz)

    return render(request, "fornecedores/fornecedor_detail.html", {
        "fornecedor": fornecedor,
        "documentos": documentos,
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
        "pontuacao_geral": pontuacao_geral,
        "ano_monitoramento": ano,
        "matriz": matriz,
        "matriz_produtos": matriz_produtos.splitlines(),
        "matriz_servicos": matriz_servicos.splitlines(),
        "matriz_respostas": matriz_respostas,
        "matriz_requisitos": ["A", "B", "C", "D"],
    })


@login_required
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


@login_required
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


# ----------------------------------------------------------------------------- perguntas
@login_required
def pergunta_list(request):
    perguntas = PerguntaAvaliacao.objects.all().order_by("tipo", "ordem", "id")
    return render(request, "fornecedores/pergunta_list.html", {"perguntas": perguntas})


@login_required
def pergunta_create(request):
    if request.method == "POST":
        form = PerguntaAvaliacaoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta cadastrada com sucesso!")
            return redirect("fornecedores:pergunta_list")
    else:
        form = PerguntaAvaliacaoForm()
    return render(request, "fornecedores/pergunta_form.html", {"form": form})


@login_required
def pergunta_edit(request, pk):
    pergunta = get_object_or_404(PerguntaAvaliacao, pk=pk)
    if request.method == "POST":
        form = PerguntaAvaliacaoForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada com sucesso!")
            return redirect("fornecedores:pergunta_list")
    else:
        form = PerguntaAvaliacaoForm(instance=pergunta)
    return render(request, "fornecedores/pergunta_form.html", {"form": form, "pergunta": pergunta})


@login_required
def pergunta_delete(request, pk):
    pergunta = get_object_or_404(PerguntaAvaliacao, pk=pk)
    total_respostas = RespostaAvaliacao.objects.filter(pergunta=pergunta).count()
    if request.method == "POST":
        if total_respostas:
            # Excluir apagaria (em cascata) as respostas de avaliações já feitas e alteraria o histórico.
            pergunta.ativo = False
            pergunta.save(update_fields=["ativo"])
            messages.warning(
                request,
                f"A pergunta possui {total_respostas} resposta(s) em avaliações já registradas e não pode ser "
                "excluída. Ela foi desativada e não aparecerá em novas avaliações.",
            )
        else:
            pergunta.delete()
            messages.success(request, "Pergunta removida com sucesso!")
        return redirect("fornecedores:pergunta_list")
    return render(request, "fornecedores/pergunta_confirm_delete.html", {
        "pergunta": pergunta, "total_respostas": total_respostas,
    })


@login_required
@require_GET
def perguntas_filtradas(request):
    tipo = request.GET.get("tipo")
    tipo_nota = request.GET.get("tipo_nota")
    if tipo not in dict(PerguntaAvaliacao.TIPO_CHOICES):
        return JsonResponse({"perguntas": []})
    perguntas = PerguntaAvaliacao.objects.filter(tipo=tipo, ativo=True)
    if tipo == "MONITORAMENTO" and tipo_nota:
        perguntas = perguntas.filter(Q(produto_servico=tipo_nota) | Q(produto_servico="AMBOS"))
    data = [
        {
            "id": p.id,
            "texto": p.texto,
            "produto_servico": p.get_produto_servico_display() if p.produto_servico else "",
        }
        for p in perguntas.order_by("ordem", "id")
    ]
    return JsonResponse({"perguntas": data})


@login_required
@require_GET
def api_respostas_avaliacao(request, avaliacao_id):
    respostas = RespostaAvaliacao.objects.filter(avaliacao_id=avaliacao_id)
    data = {r.pergunta_id: {"resposta": r.resposta, "observacao": r.observacao} for r in respostas}
    return JsonResponse({"respostas": data})


# ----------------------------------------------------------------------------- documentos
@login_required
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


@login_required
def documento_delete(request, fornecedor_id, doc_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    doc = get_object_or_404(DocumentoFornecedor, pk=doc_id, fornecedor=fornecedor)
    if request.method == "POST":
        arquivo = doc.arquivo
        doc.delete()
        try:
            arquivo.delete(save=False)  # não deixa o arquivo órfão no storage
        except Exception:  # noqa: BLE001 - falha de storage não deve impedir a remoção do registro
            pass
        messages.success(request, "Documento removido com sucesso!")
        return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    return render(request, "fornecedores/documento_confirm_delete.html", {"documento": doc, "fornecedor": fornecedor})


# ----------------------------------------------------------------------------- avaliação de seleção / reavaliação
def _avaliacao_questionario(request, fornecedor, tipo, template, classificar, mensagem_ok):
    """Fluxo comum de SELECAO e REAVALIACAO (questionário Sim/Não com pontuação percentual)."""
    perguntas = PerguntaAvaliacao.objects.filter(tipo=tipo, ativo=True).order_by("ordem", "id")
    ultima = AvaliacaoFornecedor.objects.filter(fornecedor=fornecedor, tipo=tipo).order_by("-data", "-id").first()
    detalhe = reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk])
    contexto_ultima = "ultima_avaliacao" if tipo == "SELECAO" else "ultima_reavaliacao"

    if request.method == "POST":
        data_submit, erro = _data_do_post(request)
        if erro:
            messages.error(request, erro)
        elif not perguntas.exists():
            messages.error(request, "Não há perguntas ativas cadastradas para este tipo de avaliação.")
        else:
            mesmo_dia = AvaliacaoFornecedor.objects.filter(fornecedor=fornecedor, tipo=tipo, data=data_submit).first()
            if tipo == "REAVALIACAO" and not mesmo_dia and AvaliacaoFornecedor.objects.filter(
                fornecedor=fornecedor, tipo=tipo, data__year=data_submit.year
            ).exists():
                messages.error(
                    request,
                    "Já existe uma reavaliação registrada para este ano. A próxima só poderá ser realizada "
                    "a partir de janeiro do próximo ano.",
                )
                return redirect(detalhe)
            with transaction.atomic():
                avaliacao = mesmo_dia or AvaliacaoFornecedor(
                    fornecedor=fornecedor, data=data_submit, tipo=tipo, avaliador=request.user
                )
                avaliacao.observacao = request.POST.get("observacao", "").strip()
                avaliacao.save()
                sim, nao = _salvar_respostas(avaliacao, perguntas, request.POST)
                pct = services.percentual(sim, sim + nao)
                avaliacao.pontuacao_ano = pct
                avaliacao.resultado = classificar(pct)
                avaliacao.save()
            messages.success(request, mensagem_ok)
            return redirect(detalhe)

    return render(request, template, {
        "fornecedor": fornecedor,
        "perguntas_com_respostas": _perguntas_com_respostas(perguntas, ultima),
        contexto_ultima: ultima,
        "today": timezone.localdate(),
    })


@login_required
def avaliacao_selecao_create(request, fornecedor_id):
    """Criar/editar avaliação de SELECAO (Avaliação Inicial)."""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    return _avaliacao_questionario(
        request, fornecedor, "SELECAO", "fornecedores/avaliacao_selecao_form.html",
        services.classificar_selecao, "Avaliação de Seleção registrada com sucesso!",
    )


@login_required
def avaliacao_reavaliacao_create(request, fornecedor_id):
    """Criar/editar reavaliação (REAVALIACAO): no máximo uma por ano."""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    return _avaliacao_questionario(
        request, fornecedor, "REAVALIACAO", "fornecedores/avaliacao_reavaliacao_form.html",
        services.classificar_reavaliacao, "Reavaliação registrada com sucesso!",
    )


@login_required
def reavaliacao_create(request, fornecedor_id):
    """Rota legada: a reavaliação passou a ser registrada em avaliacao_reavaliacao_create."""
    get_object_or_404(Fornecedor, pk=fornecedor_id)
    return redirect(reverse("fornecedores:avaliacao_reavaliacao_create", args=[fornecedor_id]))


# ----------------------------------------------------------------------------- monitoramento
def _salvar_monitoramento(request, fornecedor, form, perguntas, avaliacao=None):
    """Grava o registro de monitoramento e suas respostas; retorna a avaliação."""
    with transaction.atomic():
        if avaliacao is None:
            data = form.cleaned_data["data"]
            avaliacao = (
                services.monitoramentos()
                .filter(
                    fornecedor=fornecedor,
                    data=data,
                    nota_fiscal=form.cleaned_data.get("nota_fiscal") or None,
                    tipo_nota=form.cleaned_data["tipo_nota"],
                )
                .order_by("-id")
                .first()
            )
        if avaliacao is not None:  # atualização: aplica os campos do formulário
            for campo in ("data", "nota_fiscal", "tipo_nota", "observacao"):
                setattr(avaliacao, campo, form.cleaned_data.get(campo))
        else:
            avaliacao = form.save(commit=False)
            avaliacao.fornecedor = fornecedor
            avaliacao.tipo = "MONITORAMENTO"
            avaliacao.avaliador = request.user
        avaliacao.nota_fiscal = avaliacao.nota_fiscal or None
        avaliacao.save()
        _, nao = _salvar_respostas(avaliacao, perguntas, request.POST, com_observacao=True)
        avaliacao.pontuacao_ano = services.pontuacao_monitoramento(nao)
        avaliacao.resultado = services.classificar_monitoramento(avaliacao.pontuacao_ano)
        avaliacao.save()
    return avaliacao


@login_required
def avaliacao_create(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["data"] > timezone.localdate():
                form.add_error("data", "A data da avaliação não pode ser futura.")
            else:
                perguntas = _perguntas_monitoramento(form.cleaned_data["tipo_nota"])
                _salvar_monitoramento(request, fornecedor, form, perguntas)
                messages.success(request, "Avaliação registrada com sucesso!")
                return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))
    else:
        form = AvaliacaoFornecedorForm(initial={"data": timezone.localdate()})
    return render(request, "fornecedores/avaliacao_form.html", {"form": form, "fornecedor": fornecedor})


@login_required
def avaliacao_edit(request, fornecedor_id, avaliacao_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    # Somente registros de monitoramento: editar uma seleção/reavaliação aqui apagaria suas respostas.
    avaliacao = get_object_or_404(services.monitoramentos().filter(fornecedor=fornecedor), pk=avaliacao_id)
    if request.method == "POST":
        form = AvaliacaoFornecedorForm(request.POST, instance=avaliacao)
        if form.is_valid():
            if form.cleaned_data["data"] > timezone.localdate():
                form.add_error("data", "A data da avaliação não pode ser futura.")
            else:
                perguntas = _perguntas_monitoramento(form.cleaned_data["tipo_nota"])
                _salvar_monitoramento(request, fornecedor, form, perguntas, avaliacao=avaliacao)
                messages.success(request, "Avaliação atualizada com sucesso!")
                return redirect(reverse("fornecedores:avaliacao_list", args=[fornecedor.pk]))
    else:
        form = AvaliacaoFornecedorForm(instance=avaliacao)
    return render(request, "fornecedores/avaliacao_form.html", {
        "form": form, "fornecedor": fornecedor, "edicao": True, "avaliacao": avaliacao,
    })


@login_required
def avaliacao_list(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    if request.method == "POST" and request.POST.get("delete_id"):
        if not _pode(request, "fornecedores:avaliacao_edit"):
            messages.error(request, "Você não tem permissão para remover avaliações.")
        else:
            avaliacao = services.monitoramentos().filter(fornecedor=fornecedor, id=request.POST["delete_id"]).first()
            if avaliacao:
                avaliacao.delete()
                messages.success(request, "Avaliação removida com sucesso!")
        return redirect(reverse("fornecedores:avaliacao_list", args=[fornecedor.pk]))

    avaliacoes = (
        services.monitoramentos()
        .filter(fornecedor=fornecedor)
        .select_related("avaliador")
        .prefetch_related(
            models.Prefetch(
                "respostas",
                queryset=RespostaAvaliacao.objects.filter(resposta=False).select_related("pergunta"),
                to_attr="respostas_nao",
            )
        )
        .order_by("-data", "-id")
    )
    avaliacoes_info = [{"obj": av, "perguntas_nao": av.respostas_nao} for av in avaliacoes]
    return render(request, "fornecedores/avaliacao_list.html", {"avaliacoes_info": avaliacoes_info, "fornecedor": fornecedor})


# ----------------------------------------------------------------------------- reavaliações
@login_required
def reavaliacao_list(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    reavaliacoes = fornecedor.avaliacoes.filter(tipo="REAVALIACAO").order_by("-data", "-id")

    reavaliacoes_detalhes = []
    for reavaliacao in reavaliacoes:
        respostas = list(reavaliacao.respostas.select_related("pergunta").order_by("pergunta__ordem"))
        reavaliacoes_detalhes.append({
            "reavaliacao": reavaliacao,
            "respostas": respostas,
            "total_respostas": len(respostas),
            "respostas_sim": sum(1 for r in respostas if r.resposta),
        })

    return render(request, "fornecedores/reavaliacao_list.html", {
        "reavaliacoes_detalhes": reavaliacoes_detalhes,
        "fornecedor": fornecedor,
        "total_reavaliacoes": len(reavaliacoes_detalhes),
        "today": timezone.localdate(),
    })


@login_required
def reavaliacao_delete(request, fornecedor_id):
    """Deleta a última reavaliação de um fornecedor (sempre a mais recente, para manter a consistência)."""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    ultima_reavaliacao = fornecedor.avaliacoes.filter(tipo="REAVALIACAO").order_by("-data", "-id").first()

    if not ultima_reavaliacao:
        messages.error(request, "Nenhuma reavaliação encontrada para deletar.")
        return redirect("fornecedores:reavaliacao_list", fornecedor_id=fornecedor_id)

    if request.method == "POST":
        reavaliacao_data = ultima_reavaliacao.data
        ultima_reavaliacao.delete()  # respostas removidas em cascata
        messages.success(request, f"Reavaliação de {reavaliacao_data.strftime('%d/%m/%Y')} deletada com sucesso.")
        return redirect("fornecedores:reavaliacao_list", fornecedor_id=fornecedor_id)

    return render(request, "fornecedores/reavaliacao_delete_confirm.html", {
        "fornecedor": fornecedor,
        "reavaliacao": ultima_reavaliacao,
        "total_respostas": ultima_reavaliacao.respostas.count(),
    })


# ----------------------------------------------------------------------------- exportação
@login_required
def export_avaliacoes_excel(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    avaliacoes = (
        fornecedor.avaliacoes.select_related("avaliador")
        .prefetch_related("respostas__pergunta")
        .order_by("-data", "-id")
    )
    colunas_base = ["Data", "Tipo", "Avaliador", "Pontuação", "Resultado"]
    data = []
    for av in avaliacoes:
        avaliador = (av.avaliador.get_full_name() or av.avaliador.get_username()) if av.avaliador else ""
        data.append({
            "Data": av.data,
            "Tipo": av.get_tipo_display(),
            "Avaliador": avaliador,
            "Pontuação": av.pontuacao_ano,
            "Resultado": av.resultado,
            **{r.pergunta.texto: ("Sim" if r.resposta else "Não") for r in av.respostas.all()},
        })
    df = pd.DataFrame(data) if data else pd.DataFrame(columns=colunas_base)
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    nome = slugify(fornecedor.empresa) or f"fornecedor-{fornecedor.pk}"
    response["Content-Disposition"] = f'attachment; filename="avaliacoes_{nome}.xlsx"'
    df.to_excel(response, index=False)
    return response


# ----------------------------------------------------------------------------- matriz de seleção
@login_required
def avaliacao_matriz_create(request, fornecedor_id):
    """Avaliação tipo matriz com requisitos A, B, C, D para Produto e Serviço."""
    fornecedor = get_object_or_404(Fornecedor, pk=fornecedor_id)
    ultima_matriz = _ultima_matriz(fornecedor)

    if request.method == "POST":
        data, erro = _data_do_post(request)
        if erro:
            messages.error(request, erro)
        else:
            produtos = [p.strip() for p in request.POST.get("produtos", "").split("\n") if p.strip()]
            servicos = [s.strip() for s in request.POST.get("servicos", "").split("\n") if s.strip()]
            detalhes = []
            if produtos:
                detalhes.append("PRODUTOS:\n- " + "\n- ".join(produtos))
            if servicos:
                detalhes.append("SERVIÇOS:\n- " + "\n- ".join(servicos))
            observacao = "\n\n".join(filter(None, [request.POST.get("observacao", "").strip(), *detalhes]))

            with transaction.atomic():
                avaliacao = AvaliacaoFornecedor.objects.create(
                    fornecedor=fornecedor, data=data, tipo="MONITORAMENTO",
                    avaliador=request.user, observacao=observacao,
                )
                RespostaMatrizAvaliacao.objects.bulk_create([
                    RespostaMatrizAvaliacao(
                        avaliacao=avaliacao,
                        tipo=tipo,
                        nome_item="Produto" if tipo == "PRODUTO" else "Serviço",
                        requisito=requisito,
                        respondido=request.POST.get(f"matriz_{tipo}_{requisito}") == "on",
                    )
                    for tipo in ("PRODUTO", "SERVICO")
                    for requisito in ("A", "B", "C", "D")
                ])
            messages.success(request, "Avaliação de matriz registrada com sucesso!")
            return redirect(reverse("fornecedores:fornecedor_detail", args=[fornecedor.pk]))

    produtos_anteriores, servicos_anteriores, respostas_anteriores = _dados_matriz(ultima_matriz)
    return render(request, "fornecedores/avaliacao_matriz_form.html", {
        "fornecedor": fornecedor,
        "ultima_matriz": ultima_matriz,
        "produtos_anteriores": produtos_anteriores,
        "servicos_anteriores": servicos_anteriores,
        "respostas_anteriores": respostas_anteriores,
        "today": timezone.localdate(),
    })


# ----------------------------------------------------------------------------- hub
@login_required
def modulo_fornecedores_view(request):
    """HUB dedicado do Módulo de Fornecedores."""
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=DIAS_ALERTA_VALIDADE)
    context = {
        "total_fornecedores": Fornecedor.objects.count(),
        "fornecedores_ativos": Fornecedor.objects.filter(ativo=True).count(),
        "fornecedores_criticos": Fornecedor.objects.filter(tipo="CRITICO", ativo=True).count(),
        "total_avaliacoes": AvaliacaoFornecedor.objects.count(),
        "total_perguntas": PerguntaAvaliacao.objects.filter(ativo=True).count(),
        "documentos_vencidos": DocumentoFornecedor.objects.filter(
            fornecedor__ativo=True, data_validade__lt=hoje
        ).count(),
        "documentos_a_vencer": DocumentoFornecedor.objects.filter(
            fornecedor__ativo=True, data_validade__gte=hoje, data_validade__lte=limite
        ).count(),
        "fornecedores_recentes": Fornecedor.objects.filter(ativo=True).order_by("-id")[:6],
        "avaliacoes_recentes": AvaliacaoFornecedor.objects.select_related("fornecedor", "avaliador").order_by("-data", "-id")[:5],
    }
    return render(request, "fornecedores/modulo_fornecedores.html", context)
