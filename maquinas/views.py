from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CategoriaMaquinaForm, MaquinaForm
from .models import CategoriaMaquina, Maquina


@login_required
def maquinas_list(request):
    maquinas = Maquina.objects.select_related("categoria", "setor")
    filtros = {
        "q": (request.GET.get("q") or "").strip(),
        "categoria": (request.GET.get("categoria") or "").strip(),
        "status": (request.GET.get("status") or "").strip(),
    }

    if filtros["q"]:
        termo = filtros["q"]
        maquinas = maquinas.filter(
            Q(codigo__icontains=termo)
            | Q(numero_serie__icontains=termo)
            | Q(fabricante__icontains=termo)
            | Q(setor__nome__icontains=termo)
            | Q(categoria__nome__icontains=termo)
            | Q(nome__icontains=termo)
            | Q(descricao__icontains=termo)
        )

    if filtros["categoria"]:
        maquinas = maquinas.filter(categoria_id=filtros["categoria"])

    if filtros["status"] == "ativas":
        maquinas = maquinas.filter(status=True)
    elif filtros["status"] == "inativas":
        maquinas = maquinas.filter(status=False)

    context = {
        "maquinas": maquinas.order_by("codigo", "numero_serie", "fabricante"),
        "categorias": CategoriaMaquina.objects.order_by("nome"),
        "filtros": filtros,
        "total_maquinas": Maquina.objects.count(),
        "maquinas_ativas": Maquina.objects.filter(status=True).count(),
        "maquinas_inativas": Maquina.objects.filter(status=False).count(),
        "categorias_ativas": CategoriaMaquina.objects.filter(ativo=True).count(),
    }
    return render(request, "maquinas/maquinas_list.html", context)


@login_required
def maquina_create(request):
    if request.method == "POST":
        form = MaquinaForm(request.POST)
        if form.is_valid():
            maquina = form.save()
            messages.success(request, f"Maquina '{maquina}' cadastrada com sucesso.")
            return redirect("maquinas:maquinas_list")
    else:
        form = MaquinaForm()

    context = {
        "form": form,
        "titulo": "Nova maquina",
        "acao": "Cadastrar maquina",
    }
    return render(request, "maquinas/maquina_form.html", context)


@login_required
def maquina_detail(request, pk):
    maquina = get_object_or_404(Maquina.objects.select_related("categoria", "setor"), pk=pk)
    ocorrencias = maquina.ocorrencias_laboratorio_maquina.select_related(
        "categoria",
        "responsavel",
    ).order_by("-data_abertura")
    ocorrencias_abertas = ocorrencias.filter(data_encerramento__isnull=True).count()

    context = {
        "maquina": maquina,
        "ocorrencias": ocorrencias,
        "total_ocorrencias": ocorrencias.count(),
        "ocorrencias_abertas": ocorrencias_abertas,
        "ocorrencias_encerradas": ocorrencias.count() - ocorrencias_abertas,
    }
    return render(request, "maquinas/maquina_detail.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def maquina_delete(request, pk):
    maquina = get_object_or_404(Maquina.objects.select_related("categoria", "setor"), pk=pk)
    total_ocorrencias = maquina.ocorrencias_laboratorio_maquina.count()

    if request.method == "POST":
        if total_ocorrencias > 0:
            messages.error(
                request,
                f"Nao e possivel excluir a maquina '{maquina}' porque ela esta vinculada a {total_ocorrencias} ocorrencia(s) do laboratorio.",
            )
            return redirect("maquinas:maquinas_list")

        nome = str(maquina)
        maquina.delete()
        messages.success(request, f"Maquina '{nome}' excluida com sucesso.")
        return redirect("maquinas:maquinas_list")

    context = {
        "maquina": maquina,
        "total_ocorrencias": total_ocorrencias,
    }
    return render(request, "maquinas/maquina_confirm_delete.html", context)


@login_required
def maquina_update(request, pk):
    maquina = get_object_or_404(Maquina.objects.select_related("categoria", "setor"), pk=pk)

    if request.method == "POST":
        form = MaquinaForm(request.POST, instance=maquina)
        if form.is_valid():
            maquina = form.save()
            messages.success(request, f"Maquina '{maquina}' atualizada com sucesso.")
            return redirect("maquinas:maquinas_list")
    else:
        form = MaquinaForm(instance=maquina)

    context = {
        "form": form,
        "maquina": maquina,
        "titulo": f"Editar maquina: {maquina.codigo}",
        "acao": "Salvar alteracoes",
    }
    return render(request, "maquinas/maquina_form.html", context)


@login_required
def categorias_list(request):
    categorias = CategoriaMaquina.objects.annotate(total_maquinas=Count("maquinas"))
    termo = (request.GET.get("q") or "").strip()

    if termo:
        categorias = categorias.filter(
            Q(nome__icontains=termo) | Q(descricao__icontains=termo)
        )

    context = {
        "categorias": categorias.order_by("nome"),
        "busca": termo,
        "total_categorias": CategoriaMaquina.objects.count(),
        "total_ativas": CategoriaMaquina.objects.filter(ativo=True).count(),
    }
    return render(request, "maquinas/categorias_list.html", context)


@login_required
def categoria_create(request):
    if request.method == "POST":
        form = CategoriaMaquinaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoria '{categoria.nome}' cadastrada com sucesso.")
            return redirect("maquinas:categorias_list")
    else:
        form = CategoriaMaquinaForm()

    context = {
        "form": form,
        "titulo": "Nova categoria de maquina",
        "acao": "Cadastrar categoria",
    }
    return render(request, "maquinas/categoria_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def categoria_delete(request, pk):
    categoria = get_object_or_404(CategoriaMaquina, pk=pk)
    maquinas_vinculadas = list(categoria.maquinas.order_by("nome")[:5])
    total_maquinas = categoria.maquinas.count()
    remaining_maquinas = max(total_maquinas - len(maquinas_vinculadas), 0)

    if request.method == "POST":
        if total_maquinas > 0:
            messages.error(
                request,
                f"Nao e possivel excluir a categoria '{categoria.nome}' porque ela possui {total_maquinas} maquina(s) vinculada(s).",
            )
            return redirect("maquinas:categorias_list")

        nome = categoria.nome
        categoria.delete()
        messages.success(request, f"Categoria '{nome}' excluida com sucesso.")
        return redirect("maquinas:categorias_list")

    context = {
        "categoria": categoria,
        "maquinas_vinculadas": maquinas_vinculadas,
        "total_maquinas": total_maquinas,
        "remaining_maquinas": remaining_maquinas,
    }
    return render(request, "maquinas/categoria_confirm_delete.html", context)


@login_required
def categoria_update(request, pk):
    categoria = get_object_or_404(CategoriaMaquina, pk=pk)

    if request.method == "POST":
        form = CategoriaMaquinaForm(request.POST, instance=categoria)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoria '{categoria.nome}' atualizada com sucesso.")
            return redirect("maquinas:categorias_list")
    else:
        form = CategoriaMaquinaForm(instance=categoria)

    context = {
        "form": form,
        "categoria": categoria,
        "titulo": f"Editar categoria: {categoria.nome}",
        "acao": "Salvar alteracoes",
        "total_maquinas": categoria.maquinas.count(),
    }
    return render(request, "maquinas/categoria_form.html", context)