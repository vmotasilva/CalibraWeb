from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Count, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from io import BytesIO
import json

from .forms import ModeloAuditoriaForm, PerguntaAuditoriaForm, RegistroAuditoriaForm
from .models import ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria, RespostaAuditoria


def _parse_grid_itens(raw: str) -> list[str]:
    if not raw:
        return []
    itens: list[str] = []
    seen: set[str] = set()
    for line in str(raw).splitlines():
        item = line.strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        itens.append(item)
    return itens


def _get_grid_colunas_modelo(modelo: ModeloAuditoria) -> list[str]:
    return _parse_grid_itens(getattr(modelo, "grid_colunas", ""))


def _get_effective_grid_itens_for_create(modelo: ModeloAuditoria, raw_from_form: str) -> list[str]:
    """Determina as colunas/itens do GRID no momento de criar um registro."""
    cols_modelo = _get_grid_colunas_modelo(modelo)
    if cols_modelo:
        return cols_modelo
    return _parse_grid_itens(raw_from_form)


def _get_effective_grid_itens_for_edit(registro: RegistroAuditoria, raw_from_form: str) -> list[str]:
    """Determina as colunas/itens do GRID no momento de editar um registro.

    Quando o modelo tiver colunas pré-definidas, SEMPRE usa as colunas do modelo.
    Caso contrário, usa as colunas do formulário (se informadas) ou as já salvas no registro.
    """
    cols_modelo = _get_grid_colunas_modelo(registro.modelo)
    if cols_modelo:
        return cols_modelo
    from_form = _parse_grid_itens(raw_from_form)
    if from_form:
        return from_form
    return _parse_grid_itens(getattr(registro, "grid_itens", ""))


def _auditoria_is_admin(user) -> bool:
    return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))


def _make_unique_modelo_copy_nome(orig_nome: str) -> str:
    orig_nome = (orig_nome or "").strip() or "Modelo"
    base = f"{orig_nome} (Cópia)"
    nome = base
    i = 2
    while ModeloAuditoria.objects.filter(nome=nome).exists():
        nome = f"{orig_nome} (Cópia {i})"
        i += 1
    return nome


def _auditoria_can_update_modelo(user, modelo: ModeloAuditoria) -> bool:
    if _auditoria_is_admin(user):
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(modelo, "responsavel_id", None) == getattr(user, "pk", None):
        return True
    return modelo.responsaveis.filter(pk=user.pk).exists()


def _filter_modelos_para_usuario(user, qs):
    if _auditoria_is_admin(user):
        return qs
    return qs.filter(models.Q(responsaveis=user) | models.Q(responsavel=user)).distinct()


def _filter_registros_para_usuario(user, qs):
    if _auditoria_is_admin(user):
        return qs
    return qs.filter(models.Q(modelo__responsaveis=user) | models.Q(modelo__responsavel=user)).distinct()


def _get_next_pergunta_ordem(modelo_id: int) -> int:
    """Retorna a próxima ordem (max+1) para perguntas de um modelo."""
    if not modelo_id:
        return 1
    max_ordem = (
        PerguntaAuditoria.objects.filter(modelo_id=modelo_id)
        .aggregate(max_val=Max("ordem"))
        .get("max_val")
    )
    return (max_ordem or 0) + 1


@login_required
def api_next_pergunta_ordem(request):
    """API: devolve a próxima ordem para o modelo selecionado."""
    modelo_id = (request.GET.get("modelo") or "").strip()
    if not (modelo_id and modelo_id.isdigit()):
        return JsonResponse({"next": 1})
    return JsonResponse({"next": _get_next_pergunta_ordem(int(modelo_id))})


@login_required
def modulo_auditoria_view(request):
    modelos_qs = _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all())
    total_modelos = modelos_qs.count()
    total_perguntas = PerguntaAuditoria.objects.filter(modelo__in=modelos_qs).count()
    total_registros = RegistroAuditoria.objects.filter(modelo__in=modelos_qs).count()
    registros_recentes = (
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo"),
        )
        .order_by("-data_auditoria")[:5]
    )

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
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem criar modelos de auditoria.")
        return redirect("auditoria:modelos_list")
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
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para atualizar este modelo de auditoria.")
        return redirect("auditoria:modelos_list")
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
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para remover este modelo de auditoria.")
        return redirect("auditoria:modelos_list")
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
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta cadastrada com sucesso.")
            modelo_id = getattr(form.instance, "modelo_id", None)
            url = reverse("auditoria:perguntas_list")
            if modelo_id:
                url = f"{url}?modelo={modelo_id}"
            return redirect(url)
    else:
        initial = {}
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            initial["modelo"] = modelo_id
            if str(modelo_id).isdigit():
                initial["ordem"] = _get_next_pergunta_ordem(int(modelo_id))
        form = PerguntaAuditoriaForm(initial=initial)
    return render(request, "auditoria/pergunta_form.html", {"form": form, "modo": "novo"})


@login_required
def pergunta_duplicate(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    if request.method != "POST":
        return redirect("auditoria:perguntas_list")

    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    with transaction.atomic():
        nova = PerguntaAuditoria(
            modelo_id=pergunta.modelo_id,
            pergunta=pergunta.pergunta,
            tipo_resposta=pergunta.tipo_resposta,
            preenchimento_semanal=pergunta.preenchimento_semanal,
            opcoes_resposta=pergunta.opcoes_resposta,
            aplicar_no_grid=pergunta.aplicar_no_grid,
            ordem=_get_next_pergunta_ordem(pergunta.modelo_id),
            obrigatoria=pergunta.obrigatoria,
            ativo=pergunta.ativo,
        )
        nova.save()

    messages.success(request, "Pergunta duplicada com sucesso.")
    url = reverse("auditoria:perguntas_list")
    if pergunta.modelo_id:
        url = f"{url}?modelo={pergunta.modelo_id}"
    return redirect(url)


@login_required
def modelo_duplicate(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem criar modelos de auditoria.")
        return redirect("auditoria:modelos_list")
    if request.method != "POST":
        return redirect("auditoria:modelos_list")

    modelo = get_object_or_404(ModeloAuditoria, pk=pk)

    with transaction.atomic():
        novo_modelo = ModeloAuditoria(
            nome=_make_unique_modelo_copy_nome(modelo.nome),
            objeto_auditoria=modelo.objeto_auditoria,
            link_sharepoint=modelo.link_sharepoint,
            periodicidade=modelo.periodicidade,
            dia_semana=modelo.dia_semana,
            dias_quinzenal=modelo.dias_quinzenal,
            dia_mes=modelo.dia_mes,
            responsavel_id=modelo.responsavel_id,
            preenchimento_grid=modelo.preenchimento_grid,
            grid_rotulo_item=modelo.grid_rotulo_item,
            grid_colunas=modelo.grid_colunas,
            ativo=modelo.ativo,
        )
        novo_modelo.save()
        novo_modelo.responsaveis.set(modelo.responsaveis.all())

        perguntas = list(modelo.perguntas.all().order_by("ordem", "id"))
        novas_perguntas = [
            PerguntaAuditoria(
                modelo=novo_modelo,
                pergunta=p.pergunta,
                tipo_resposta=p.tipo_resposta,
                preenchimento_semanal=p.preenchimento_semanal,
                opcoes_resposta=p.opcoes_resposta,
                aplicar_no_grid=p.aplicar_no_grid,
                ordem=p.ordem,
                obrigatoria=p.obrigatoria,
                ativo=p.ativo,
            )
            for p in perguntas
        ]
        if novas_perguntas:
            PerguntaAuditoria.objects.bulk_create(novas_perguntas)

    messages.success(request, "Modelo duplicado com sucesso.")
    return redirect("auditoria:modelos_list")


@login_required
def pergunta_edit(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada com sucesso.")
            modelo_id = getattr(form.instance, "modelo_id", None)
            url = reverse("auditoria:perguntas_list")
            if modelo_id:
                url = f"{url}?modelo={modelo_id}"
            return redirect(url)
    else:
        form = PerguntaAuditoriaForm(instance=pergunta)
    return render(request, "auditoria/pergunta_form.html", {"form": form, "modo": "edicao", "pergunta": pergunta})


@login_required
def pergunta_delete(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("auditoria:perguntas_list")
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

    registros = _filter_registros_para_usuario(
        request.user,
        RegistroAuditoria.objects.select_related("modelo", "avaliador"),
    )
    if inicio:
        registros = registros.filter(data_auditoria__gte=inicio)
    if fim:
        registros = registros.filter(data_auditoria__lte=fim)
    if modelo_id:
        registros = registros.filter(modelo_id=modelo_id)

    context = {
        "registros": registros.order_by("-data_auditoria", "-id"),
        "modelos": _filter_modelos_para_usuario(
            request.user,
            ModeloAuditoria.objects.filter(ativo=True),
        ).order_by("nome"),
        "inicio": inicio,
        "fim": fim,
        "modelo_id": modelo_id,
    }
    return render(request, "auditoria/registros_list.html", context)


@login_required
def selecionar_modelo_preenchimento(request):
    """Lista modelos ativos para o usuário escolher qual preencher"""
    q = (request.GET.get("q") or "").strip()
    responsavel_id = (request.GET.get("responsavel") or "").strip()
    periodicidade = (request.GET.get("periodicidade") or "").strip()

    if not _auditoria_is_admin(request.user):
        responsavel_id = str(request.user.pk)

    modelos = _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.filter(ativo=True))
    if q:
        modelos = modelos.filter(models.Q(nome__icontains=q) | models.Q(objeto_auditoria__icontains=q))
    if responsavel_id:
        modelos = modelos.filter(
            models.Q(responsaveis__id=responsavel_id) | models.Q(responsavel_id=responsavel_id)
        ).distinct()
    if periodicidade:
        modelos = modelos.filter(periodicidade=periodicidade)

    modelos = modelos.annotate(
        total_perguntas=Count("perguntas", filter=models.Q(perguntas__ativo=True))
    ).order_by("nome")

    User = get_user_model()
    modelos_com_responsavel = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(
            ativo=True,
        ).filter(
            models.Q(responsaveis__isnull=False) | models.Q(responsavel__isnull=False)
        ),
    )
    ids_m2m = list(modelos_com_responsavel.values_list("responsaveis__id", flat=True))
    ids_fk = list(modelos_com_responsavel.values_list("responsavel_id", flat=True))
    responsaveis_ids = {i for i in ids_m2m + ids_fk if i}
    responsaveis = User.objects.filter(id__in=responsaveis_ids).order_by("username")

    context = {
        "modelos": modelos,
        "q": q,
        "responsavel_id": responsavel_id,
        "periodicidade": periodicidade,
        "periodicidade_choices": ModeloAuditoria.PERIODICIDADE_CHOICES,
        "responsaveis": responsaveis,
    }
    return render(request, "auditoria/selecionar_modelo.html", context)


@login_required
def registro_create(request, modelo_id=None):
    """Cria novo registro de auditoria para um modelo específico"""
    modelos_qs = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(ativo=True),
    )

    if modelo_id:
        modelo = get_object_or_404(modelos_qs, pk=modelo_id)
    else:
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            modelo = get_object_or_404(modelos_qs, pk=modelo_id)
        else:
            return redirect("auditoria:selecionar_modelo_preenchimento")
    
    perguntas = PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("ordem", "id")
    
    dias_semana_choices = list(ModeloAuditoria.DIA_SEMANA_CHOICES)
    is_semanal = modelo.periodicidade == "SEMANAL"
    is_diaria_ou_unica = modelo.periodicidade in ("DIARIA", "UNICA")
    grid_enabled = bool(getattr(modelo, "preenchimento_grid", False) or _get_grid_colunas_modelo(modelo))

    perguntas_por_dia = [
        p for p in perguntas if is_semanal and getattr(p, "preenchimento_semanal", "UNICO") == "POR_DIA"
    ]
    # Em modo GRID com colunas/itens definidos, repetimos o conjunto de perguntas por coluna.
    # (Neste modo, não filtramos por "aplicar_no_grid".)
    grid_perguntas = [p for p in perguntas if p not in perguntas_por_dia]

    if request.method == "POST":
        post_data = request.POST
        if is_diaria_ou_unica:
            # Forçar período = data da auditoria (mesmo se vier em branco)
            post_data = request.POST.copy()
            data_auditoria = (post_data.get("data_auditoria") or "").strip()
            if data_auditoria:
                post_data["periodo_inicio"] = data_auditoria
                post_data["periodo_fim"] = data_auditoria

        form = RegistroAuditoriaForm(post_data)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.modelo = modelo
            registro.avaliador = request.user

            grid_itens = []
            if grid_enabled:
                grid_itens = _get_effective_grid_itens_for_create(modelo, form.cleaned_data.get("grid_itens") or "")
                registro.grid_itens = "\n".join(grid_itens)

            registro.save()

            # Salvar respostas
            erros = []

            # Perguntas padrão (não-POR_DIA)
            if grid_enabled and grid_itens:
                for pergunta in grid_perguntas:
                    for idx, item in enumerate(grid_itens):
                        field_name = f"grid_{pergunta.id}_{idx}"
                        valor = request.POST.get(field_name, "").strip()
                        if not valor and pergunta.obrigatoria:
                            erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória para {item}.")
                        RespostaAuditoria.objects.create(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana=None,
                            grid_item=item,
                            valor=valor,
                        )
            else:
                for pergunta in grid_perguntas:
                    valor = request.POST.get(f"resposta_{pergunta.id}", "").strip()
                    if not valor and pergunta.obrigatoria:
                        erros.append(f"A pergunta '{pergunta.pergunta}' é obrigatória.")
                    RespostaAuditoria.objects.create(
                        registro=registro,
                        pergunta=pergunta,
                        dia_semana=None,
                        grid_item="",
                        valor=valor,
                    )

            # Perguntas POR_DIA: no GRID, também repetimos por item/coluna.
            for pergunta in perguntas_por_dia:
                if grid_enabled and grid_itens:
                    for idx, item in enumerate(grid_itens):
                        for dia_key, _dia_label in dias_semana_choices:
                            field_name = f"griddia_{pergunta.id}_{idx}_{dia_key}"
                            valor = request.POST.get(field_name, "").strip()
                            if not valor and pergunta.obrigatoria:
                                erros.append(
                                    f"A pergunta '{pergunta.pergunta}' é obrigatória para {item} em {dict(dias_semana_choices).get(dia_key, dia_key)}."
                                )
                            RespostaAuditoria.objects.create(
                                registro=registro,
                                pergunta=pergunta,
                                dia_semana=dia_key,
                                grid_item=item,
                                valor=valor,
                            )
                else:
                    for dia_key, _dia_label in dias_semana_choices:
                        field_name = f"resposta_{pergunta.id}_{dia_key}"
                        valor = request.POST.get(field_name, "").strip()
                        if not valor and pergunta.obrigatoria:
                            erros.append(
                                f"A pergunta '{pergunta.pergunta}' é obrigatória para {dict(dias_semana_choices).get(dia_key, dia_key)}."
                            )
                        RespostaAuditoria.objects.create(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana=dia_key,
                            grid_item="",
                            valor=valor,
                        )
            
            if erros:
                for erro in erros:
                    messages.warning(request, erro)
            
            messages.success(request, "Formulário de auditoria preenchido com sucesso!")
            return redirect("auditoria:registro_detail", pk=registro.pk)
    else:
        from datetime import date
        initial = {"data_auditoria": date.today()}
        if is_diaria_ou_unica:
            initial["periodo_inicio"] = initial["data_auditoria"]
            initial["periodo_fim"] = initial["data_auditoria"]
        form = RegistroAuditoriaForm(initial=initial)

    grid_itens = []
    if grid_enabled:
        raw_grid_itens = (getattr(form, "data", {}) or {}).get("grid_itens") or ""
        grid_itens = _get_effective_grid_itens_for_create(modelo, raw_grid_itens)
    grid_colunas_predefinidas = bool(_get_grid_colunas_modelo(modelo))

    context = {
        "form": form,
        "modelo": modelo,
        "perguntas": perguntas,
        "grid_enabled": grid_enabled,
        "grid_itens": grid_itens,
        "grid_colunas_predefinidas": grid_colunas_predefinidas,
        "grid_perguntas": grid_perguntas,
        "perguntas_por_dia": perguntas_por_dia,
        "dias_semana_choices": dias_semana_choices,
    }
    return render(request, "auditoria/registro_form.html", context)


@login_required
def registro_edit(request, pk):
    """Edita um registro de auditoria existente"""
    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo"),
        ),
        pk=pk,
    )
    perguntas = PerguntaAuditoria.objects.filter(modelo=registro.modelo, ativo=True).order_by("ordem", "id")
    
    dias_semana_choices = list(ModeloAuditoria.DIA_SEMANA_CHOICES)
    is_semanal = registro.modelo.periodicidade == "SEMANAL"
    is_diaria_ou_unica = registro.modelo.periodicidade in ("DIARIA", "UNICA")
    grid_enabled = bool(getattr(registro.modelo, "preenchimento_grid", False) or _get_grid_colunas_modelo(registro.modelo))

    perguntas_por_dia = [
        p for p in perguntas if is_semanal and getattr(p, "preenchimento_semanal", "UNICO") == "POR_DIA"
    ]
    grid_perguntas = [p for p in perguntas if p not in perguntas_por_dia]

    if request.method == "POST":
        post_data = request.POST
        if is_diaria_ou_unica:
            post_data = request.POST.copy()
            data_auditoria = (post_data.get("data_auditoria") or "").strip()
            if data_auditoria:
                post_data["periodo_inicio"] = data_auditoria
                post_data["periodo_fim"] = data_auditoria

        form = RegistroAuditoriaForm(post_data, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)

            grid_itens = []
            if grid_enabled:
                grid_itens = _get_effective_grid_itens_for_edit(registro, form.cleaned_data.get("grid_itens") or "")
                registro.grid_itens = "\n".join(grid_itens)

            registro.save()
            grid_item_to_index = {item: idx for idx, item in enumerate(grid_itens)}

            # Atualizar respostas existentes
            for pergunta in perguntas:
                is_por_dia = is_semanal and getattr(pergunta, "preenchimento_semanal", "UNICO") == "POR_DIA"

                if is_por_dia:
                    # Se antes era resposta única, remover para evitar duplicidade
                    RespostaAuditoria.objects.filter(
                        registro=registro,
                        pergunta=pergunta,
                        dia_semana__isnull=True,
                    ).delete()

                    if grid_enabled and grid_itens:
                        # Recriar POR_DIA por item/coluna
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=False,
                        ).delete()

                        for idx, item in enumerate(grid_itens):
                            for dia_key, _dia_label in dias_semana_choices:
                                field_name = f"griddia_{pergunta.id}_{idx}_{dia_key}"
                                valor = request.POST.get(field_name, "").strip()
                                RespostaAuditoria.objects.update_or_create(
                                    registro=registro,
                                    pergunta=pergunta,
                                    dia_semana=dia_key,
                                    grid_item=item,
                                    defaults={"valor": valor},
                                )
                    else:
                        # POR_DIA sem GRID
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=False,
                        ).exclude(grid_item="").delete()

                        for dia_key, _dia_label in dias_semana_choices:
                            field_name = f"resposta_{pergunta.id}_{dia_key}"
                            valor = request.POST.get(field_name, "").strip()
                            RespostaAuditoria.objects.update_or_create(
                                registro=registro,
                                pergunta=pergunta,
                                dia_semana=dia_key,
                                grid_item="",
                                defaults={"valor": valor},
                            )
                else:
                    # Se antes era por dia, remover linhas por dia
                    RespostaAuditoria.objects.filter(
                        registro=registro,
                        pergunta=pergunta,
                        dia_semana__isnull=False,
                    ).delete()

                    # GRID
                    if grid_enabled and grid_itens and pergunta in grid_perguntas:
                        # Remover itens que não existem mais
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=True,
                        ).exclude(grid_item__in=grid_itens).delete()

                        for idx, item in enumerate(grid_itens):
                            field_name = f"grid_{pergunta.id}_{idx}"
                            valor = request.POST.get(field_name, "").strip()
                            RespostaAuditoria.objects.update_or_create(
                                registro=registro,
                                pergunta=pergunta,
                                dia_semana=None,
                                grid_item=item,
                                defaults={"valor": valor},
                            )
                    else:
                        # Remover possíveis respostas GRID antigas para esta pergunta
                        RespostaAuditoria.objects.filter(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana__isnull=True,
                        ).exclude(grid_item="").delete()

                        valor = request.POST.get(f"resposta_{pergunta.id}", "").strip()
                        RespostaAuditoria.objects.update_or_create(
                            registro=registro,
                            pergunta=pergunta,
                            dia_semana=None,
                            grid_item="",
                            defaults={"valor": valor},
                        )
            
            messages.success(request, "Registro de auditoria atualizado com sucesso!")
            return redirect("auditoria:registro_detail", pk=registro.pk)
    else:
        form = RegistroAuditoriaForm(instance=registro)
        # Preencher valores atuais das respostas
        respostas_atuais = {}

        grid_itens = _get_effective_grid_itens_for_edit(registro, getattr(registro, "grid_itens", "")) if grid_enabled else []
        grid_item_to_index = {item: idx for idx, item in enumerate(grid_itens)}

        for resposta in registro.respostas.all():
            if resposta.dia_semana:
                if grid_enabled and grid_itens and getattr(resposta, "grid_item", ""):
                    idx = grid_item_to_index.get(resposta.grid_item)
                    if idx is not None:
                        respostas_atuais[f"griddia_{resposta.pergunta_id}_{idx}_{resposta.dia_semana}"] = resposta.valor
                else:
                    respostas_atuais[f"resposta_{resposta.pergunta_id}_{resposta.dia_semana}"] = resposta.valor
            elif getattr(resposta, "grid_item", ""):
                idx = grid_item_to_index.get(resposta.grid_item)
                if idx is not None:
                    respostas_atuais[f"grid_{resposta.pergunta_id}_{idx}"] = resposta.valor
            else:
                respostas_atuais[f"resposta_{resposta.pergunta_id}"] = resposta.valor

    context = {
        "form": form,
        "modelo": registro.modelo,
        "perguntas": perguntas,
        "grid_enabled": grid_enabled,
        "grid_itens": grid_itens,
        "grid_colunas_predefinidas": bool(_get_grid_colunas_modelo(registro.modelo)),
        "grid_perguntas": grid_perguntas,
        "perguntas_por_dia": perguntas_por_dia,
        "registro": registro,
        "respostas_atuais": respostas_atuais,
        "edicao": True,
        "dias_semana_choices": dias_semana_choices,
    }
    return render(request, "auditoria/registro_form.html", context)


@login_required
def registro_detail(request, pk):
    registro = get_object_or_404(
        _filter_registros_para_usuario(
            request.user,
            RegistroAuditoria.objects.select_related("modelo", "avaliador"),
        ),
        pk=pk,
    )
    respostas = registro.respostas.select_related("pergunta").order_by("pergunta__ordem", "id")
    exibir_dia_semana = respostas.filter(dia_semana__isnull=False).exists()
    total_respostas = respostas.count()
    preenchidas = respostas.exclude(valor="").count()
    percentual_preenchimento = round((preenchidas / total_respostas) * 100, 1) if total_respostas else 0

    context = {
        "registro": registro,
        "respostas": respostas,
        "exibir_dia_semana": exibir_dia_semana,
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
    responsavel_id = request.GET.get("responsavel")

    registros = _filter_registros_para_usuario(
        request.user,
        RegistroAuditoria.objects.select_related("modelo"),
    )

    if modelo_id:
        registros = registros.filter(modelo_id=modelo_id)
    if responsavel_id:
        registros = registros.filter(
            models.Q(modelo__responsaveis__id=responsavel_id) | models.Q(modelo__responsavel_id=responsavel_id)
        ).distinct()
    if inicio:
        registros = registros.filter(data_auditoria__gte=inicio)
    if fim:
        registros = registros.filter(data_auditoria__lte=fim)

    total_modelos = registros.values("modelo_id").distinct().count()
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
    todos_modelos = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(ativo=True),
    ).order_by("nome")
    modelo_selecionado = None
    if modelo_id:
        modelo_selecionado = ModeloAuditoria.objects.filter(pk=modelo_id).first()

    # Lista de responsáveis (usuários vinculados aos modelos)
    User = get_user_model()
    modelos_com_responsavel = _filter_modelos_para_usuario(
        request.user,
        ModeloAuditoria.objects.filter(
            models.Q(responsaveis__isnull=False) | models.Q(responsavel__isnull=False)
        ),
    )
    ids_m2m = list(modelos_com_responsavel.values_list("responsaveis__id", flat=True))
    ids_fk = list(modelos_com_responsavel.values_list("responsavel_id", flat=True))
    responsavel_ids = {i for i in ids_m2m + ids_fk if i}
    responsaveis = User.objects.filter(pk__in=responsavel_ids).order_by("username")
    responsavel_selecionado = None
    if responsavel_id:
        responsavel_selecionado = User.objects.filter(pk=responsavel_id).first()

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
        "responsavel_id": responsavel_id,
        "todos_modelos": todos_modelos,
        "modelo_selecionado": modelo_selecionado,
        "responsaveis": responsaveis,
        "responsavel_selecionado": responsavel_selecionado,
    }
    return render(request, "auditoria/dashboard_auditoria.html", context)


@login_required
def registros_por_modelo(request, modelo_id):
    """Lista todos os registros preenchidos de um modelo específico"""
    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )
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

    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )

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

    dias_semana_choices = list(ModeloAuditoria.DIA_SEMANA_CHOICES)
    is_semanal = modelo.periodicidade == "SEMANAL"

    # Mapear respostas por registro/pergunta/(dia)
    respostas_por_registro: dict[int, dict[tuple[int, str | None], str]] = {}
    for registro in registros:
        respostas_por_registro[registro.id] = {}
        for resposta in getattr(registro, "respostas").all():
            key = (resposta.pergunta_id, resposta.dia_semana)
            respostas_por_registro[registro.id][key] = resposta.valor

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
    for p in perguntas:
        if is_semanal and getattr(p, "preenchimento_semanal", "UNICO") == "POR_DIA":
            for dia_key, dia_label in dias_semana_choices:
                headers.append(f"{p.pergunta} ({dia_label})")
        else:
            headers.append(p.pergunta)
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
            if is_semanal and getattr(pergunta, "preenchimento_semanal", "UNICO") == "POR_DIA":
                for dia_key, _dia_label in dias_semana_choices:
                    valor = respostas_dict.get((pergunta.id, dia_key), "")
                    if pergunta.tipo_resposta in ["SIM_NAO", "BOOLEANO"]:
                        row.append(_normalize_sim_nao(valor))
                    else:
                        row.append(valor or "")
            else:
                valor = respostas_dict.get((pergunta.id, None), "")
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
