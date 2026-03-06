from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Count, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.urls import reverse
from django.views.decorators.http import require_POST
from urllib.parse import urlencode
from io import BytesIO
import json

from .forms import ComentarioInsumosForm, ModeloAuditoriaForm, PerguntaAuditoriaForm, RegistroAuditoriaForm
from .models import ComentarioInsumos, ModeloAuditoria, PerguntaAuditoria, RegistroAuditoria, RespostaAuditoria


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
    return render(request, "insumos/modulo_auditoria.html", context)


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
    return render(request, "insumos/modelos_list.html", context)


@login_required
def modelo_create(request):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem criar modelos de insumos.")
        return redirect("insumos:modelos_list")
    if request.method == "POST":
        form = ModeloAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de insumos criado com sucesso.")
            return redirect("insumos:modelos_list")
    else:
        form = ModeloAuditoriaForm()
    return render(request, "insumos/modelo_form.html", {"form": form, "modo": "novo"})


@login_required
def modelo_edit(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para atualizar este modelo de insumos.")
        return redirect("insumos:modelos_list")
    if request.method == "POST":
        form = ModeloAuditoriaForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo de insumos atualizado com sucesso.")
            return redirect("insumos:modelos_list")
    else:
        form = ModeloAuditoriaForm(instance=modelo)
    return render(request, "insumos/modelo_form.html", {"form": form, "modo": "edicao", "modelo": modelo})


@login_required
def modelo_delete(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_can_update_modelo(request.user, modelo):
        messages.error(request, "Você não tem permissão para remover este modelo de insumos.")
        return redirect("insumos:modelos_list")
    if request.method == "POST":
        modelo.delete()
        messages.success(request, "Modelo removido com sucesso.")
        return redirect("insumos:modelos_list")
    return render(request, "insumos/modelo_confirm_delete.html", {"modelo": modelo})


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
    return render(request, "insumos/perguntas_list.html", context)


def _normalize_perguntas_ordem(modelo_id: int) -> None:
    """Garante que as perguntas de um modelo tenham ordem sequencial (1..n)."""
    qs = (
        PerguntaAuditoria.objects.filter(modelo_id=modelo_id)
        .only("id", "ordem")
        .order_by("ordem", "id")
    )
    to_update = []
    expected = 1
    for p in qs:
        if p.ordem != expected:
            p.ordem = expected
            to_update.append(p)
        expected += 1
    if to_update:
        PerguntaAuditoria.objects.bulk_update(to_update, ["ordem"])


def _safe_return_to(raw: str | None) -> str:
    if raw and isinstance(raw, str) and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return redirect("insumos:perguntas_list").url


def _unique_modelo_nome(base_nome: str) -> str:
    """Gera um nome único para ModeloAuditoria respeitando max_length=150 (nome é unique)."""
    raw = (base_nome or "").strip() or "Modelo"
    suffix = " (Cópia)"

    candidate = f"{raw}{suffix}"[:150]
    if not ModeloAuditoria.objects.filter(nome=candidate).exists():
        return candidate

    idx = 2
    while True:
        tail = f"{suffix} {idx}"
        candidate = f"{raw[: max(0, 150 - len(tail))]}{tail}".strip()
        if not ModeloAuditoria.objects.filter(nome=candidate).exists():
            return candidate
        idx += 1


@login_required
@require_POST
def modelo_duplicate(request, pk):
    modelo = get_object_or_404(ModeloAuditoria, pk=pk)
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem duplicar modelos de insumos.")
        return redirect("insumos:modelos_list")

    with transaction.atomic():
        novo = ModeloAuditoria.objects.create(
            nome=_unique_modelo_nome(modelo.nome),
            objeto_auditoria=modelo.objeto_auditoria,
            link_sharepoint=modelo.link_sharepoint,
            periodicidade=modelo.periodicidade,
            dia_semana=modelo.dia_semana,
            dias_quinzenal=modelo.dias_quinzenal,
            dia_mes=modelo.dia_mes,
            responsavel=modelo.responsavel,
            preenchimento_grid=modelo.preenchimento_grid,
            grid_rotulo_item=modelo.grid_rotulo_item,
            grid_colunas=modelo.grid_colunas,
            ativo=modelo.ativo,
        )

        novo.responsaveis.set(modelo.responsaveis.all())

        perguntas_src = list(PerguntaAuditoria.objects.filter(modelo=modelo).order_by("ordem", "id"))
        perguntas_new = [
            PerguntaAuditoria(
                modelo=novo,
                pergunta=p.pergunta,
                tipo_resposta=p.tipo_resposta,
                preenchimento_semanal=p.preenchimento_semanal,
                opcoes_resposta=p.opcoes_resposta,
                aplicar_no_grid=p.aplicar_no_grid,
                ordem=p.ordem,
                obrigatoria=p.obrigatoria,
                ativo=p.ativo,
            )
            for p in perguntas_src
        ]
        if perguntas_new:
            PerguntaAuditoria.objects.bulk_create(perguntas_new)
            _normalize_perguntas_ordem(novo.id)

    messages.success(request, "Modelo duplicado com sucesso (incluindo perguntas).")
    return redirect("insumos:modelo_edit", pk=novo.id)


@login_required
def pergunta_move_up(request, pk):
    if request.method != "POST":
        return redirect("insumos:perguntas_list")
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem reordenar perguntas.")
        return redirect("insumos:perguntas_list")

    return_to = _safe_return_to(request.POST.get("return_to"))

    with transaction.atomic():
        try:
            pergunta = PerguntaAuditoria.objects.select_for_update().select_related("modelo").get(pk=pk)
        except PerguntaAuditoria.DoesNotExist:
            return redirect(return_to)
        _normalize_perguntas_ordem(pergunta.modelo_id)

        prev_q = (
            PerguntaAuditoria.objects.select_for_update()
            .filter(modelo_id=pergunta.modelo_id)
            .filter(
                models.Q(ordem__lt=pergunta.ordem)
                | (models.Q(ordem=pergunta.ordem) & models.Q(id__lt=pergunta.id))
            )
            .order_by("-ordem", "-id")
            .first()
        )

        if not prev_q:
            return redirect(return_to)

        pergunta_ordem = pergunta.ordem
        pergunta.ordem = prev_q.ordem
        prev_q.ordem = pergunta_ordem
        PerguntaAuditoria.objects.bulk_update([pergunta, prev_q], ["ordem"])
        _normalize_perguntas_ordem(pergunta.modelo_id)

    return redirect(return_to)


@login_required
def pergunta_move_down(request, pk):
    if request.method != "POST":
        return redirect("insumos:perguntas_list")
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem reordenar perguntas.")
        return redirect("insumos:perguntas_list")

    return_to = _safe_return_to(request.POST.get("return_to"))

    with transaction.atomic():
        try:
            pergunta = PerguntaAuditoria.objects.select_for_update().select_related("modelo").get(pk=pk)
        except PerguntaAuditoria.DoesNotExist:
            return redirect(return_to)
        _normalize_perguntas_ordem(pergunta.modelo_id)

        next_q = (
            PerguntaAuditoria.objects.select_for_update()
            .filter(modelo_id=pergunta.modelo_id)
            .filter(
                models.Q(ordem__gt=pergunta.ordem)
                | (models.Q(ordem=pergunta.ordem) & models.Q(id__gt=pergunta.id))
            )
            .order_by("ordem", "id")
            .first()
        )

        if not next_q:
            return redirect(return_to)

        pergunta_ordem = pergunta.ordem
        pergunta.ordem = next_q.ordem
        next_q.ordem = pergunta_ordem
        PerguntaAuditoria.objects.bulk_update([pergunta, next_q], ["ordem"])
        _normalize_perguntas_ordem(pergunta.modelo_id)

    return redirect(return_to)


@login_required
def pergunta_create(request):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("insumos:perguntas_list")
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta cadastrada com sucesso.")
            return redirect("insumos:perguntas_list")
    else:
        initial = {}
        modelo_id = request.GET.get("modelo")
        if modelo_id:
            initial["modelo"] = modelo_id
            if str(modelo_id).isdigit():
                initial["ordem"] = _get_next_pergunta_ordem(int(modelo_id))
        form = PerguntaAuditoriaForm(initial=initial)
    return render(request, "insumos/pergunta_form.html", {"form": form, "modo": "novo"})


@login_required
def pergunta_edit(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("insumos:perguntas_list")
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        form = PerguntaAuditoriaForm(request.POST, instance=pergunta)
        if form.is_valid():
            form.save()
            messages.success(request, "Pergunta atualizada com sucesso.")
            return redirect("insumos:perguntas_list")
    else:
        form = PerguntaAuditoriaForm(instance=pergunta)
    return render(request, "insumos/pergunta_form.html", {"form": form, "modo": "edicao", "pergunta": pergunta})


@login_required
def pergunta_delete(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem gerenciar perguntas.")
        return redirect("insumos:perguntas_list")
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)
    if request.method == "POST":
        pergunta.delete()
        messages.success(request, "Pergunta removida com sucesso.")
        return redirect("insumos:perguntas_list")
    return render(request, "insumos/pergunta_confirm_delete.html", {"pergunta": pergunta})


@login_required
@require_POST
def pergunta_duplicate(request, pk):
    if not _auditoria_is_admin(request.user):
        messages.error(request, "Apenas usuários Staff/Superuser podem duplicar perguntas.")
        return redirect("insumos:perguntas_list")

    return_to = _safe_return_to(request.POST.get("return_to"))
    pergunta = get_object_or_404(PerguntaAuditoria, pk=pk)

    base_text = (pergunta.pergunta or "").strip()
    suffix = " (Cópia)"
    if len(base_text) + len(suffix) <= 255:
        new_text = f"{base_text}{suffix}"
    else:
        new_text = f"{base_text[: max(0, 255 - len(suffix))]}{suffix}".strip()

    PerguntaAuditoria.objects.create(
        modelo=pergunta.modelo,
        pergunta=new_text,
        tipo_resposta=pergunta.tipo_resposta,
        preenchimento_semanal=pergunta.preenchimento_semanal,
        opcoes_resposta=pergunta.opcoes_resposta,
        aplicar_no_grid=pergunta.aplicar_no_grid,
        ordem=_get_next_pergunta_ordem(pergunta.modelo_id),
        obrigatoria=pergunta.obrigatoria,
        ativo=pergunta.ativo,
    )
    _normalize_perguntas_ordem(pergunta.modelo_id)

    messages.success(request, "Pergunta duplicada com sucesso.")
    return redirect(return_to)


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
    return render(request, "insumos/registros_list.html", context)


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
    return render(request, "insumos/selecionar_modelo.html", context)


@login_required
def registro_create(request, modelo_id=None):
    """Cria novo registro para um modelo específico"""
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
            return redirect("insumos:selecionar_modelo_preenchimento")

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
            # Forçar período = data (mesmo se vier em branco)
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

            messages.success(request, "Formulário preenchido com sucesso!")
            return redirect("insumos:registro_detail", pk=registro.pk)
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
    return render(request, "insumos/registro_form.html", context)


@login_required
def registro_edit(request, pk):
    """Edita um registro existente"""
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
    grid_enabled = bool(
        getattr(registro.modelo, "preenchimento_grid", False) or _get_grid_colunas_modelo(registro.modelo)
    )

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

            messages.success(request, "Registro atualizado com sucesso!")
            return redirect("insumos:registro_detail", pk=registro.pk)
    else:
        form = RegistroAuditoriaForm(instance=registro)
        # Preencher valores atuais das respostas
        respostas_atuais = {}

        grid_itens = (
            _get_effective_grid_itens_for_edit(registro, getattr(registro, "grid_itens", "")) if grid_enabled else []
        )
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
    return render(request, "insumos/registro_form.html", context)


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
    return render(request, "insumos/registro_detail.html", context)


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
    return render(request, "insumos/dashboard_auditoria.html", context)


@login_required
def registros_por_modelo(request, modelo_id):
    """Lista todos os registros preenchidos de um modelo específico"""
    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )

    if request.method == "POST" and (request.POST.get("action") or "").strip() == "add_comment":
        texto = (request.POST.get("comentario") or "").strip()
        if not texto:
            messages.error(request, "Informe um comentário.")
        elif len(texto) > 8000:
            messages.error(request, "Comentário muito longo (máx. 8000 caracteres).")
        else:
            ComentarioInsumos.objects.create(modelo=modelo, autor=request.user, texto=texto)
            messages.success(request, "Comentário adicionado com sucesso.")

        redirect_url = reverse("insumos:registros_por_modelo", args=[modelo.id])
        preserved = {}
        for k in ("inicio", "fim", "page", "per_page"):
            v = (request.GET.get(k) or "").strip()
            if v:
                preserved[k] = v
        if preserved:
            redirect_url = f"{redirect_url}?{urlencode(preserved)}"
        return redirect(redirect_url)

    inicio_raw = (request.GET.get("inicio") or "").strip()
    fim_raw = (request.GET.get("fim") or "").strip()
    inicio = parse_date(inicio_raw) if inicio_raw else None
    fim = parse_date(fim_raw) if fim_raw else None

    per_page_raw = (request.GET.get("per_page") or "").strip()
    allowed_per_page = {10, 25, 50, 100}
    try:
        per_page = int(per_page_raw) if per_page_raw else 25
    except (TypeError, ValueError):
        per_page = 25
    if per_page not in allowed_per_page:
        per_page = 25

    registros_qs = RegistroAuditoria.objects.filter(modelo=modelo)
    if inicio:
        registros_qs = registros_qs.filter(data_auditoria__gte=inicio)
    if fim:
        registros_qs = registros_qs.filter(data_auditoria__lte=fim)

    registros_qs = registros_qs.select_related("avaliador").order_by("-criado_em", "-id")

    paginator = Paginator(registros_qs, per_page)
    page_obj = paginator.get_page((request.GET.get("page") or "").strip() or 1)

    base_params = {}
    if inicio_raw:
        base_params["inicio"] = inicio_raw
    if fim_raw:
        base_params["fim"] = fim_raw
    base_params["per_page"] = str(per_page)
    querystring_base = urlencode(base_params)
    querystring_with_page = querystring_base
    if querystring_with_page:
        querystring_with_page = f"{querystring_with_page}&page={page_obj.number}"
    else:
        querystring_with_page = f"page={page_obj.number}"

    comentarios_qs = ComentarioInsumos.objects.filter(modelo=modelo).select_related("autor")
    if inicio:
        comentarios_qs = comentarios_qs.filter(criado_em__date__gte=inicio)
    if fim:
        comentarios_qs = comentarios_qs.filter(criado_em__date__lte=fim)
    comentarios = list(comentarios_qs.order_by("-criado_em", "-id"))

    perguntas = list(PerguntaAuditoria.objects.filter(modelo=modelo, ativo=True).order_by("ordem", "id"))
    respostas_qs = (
        RespostaAuditoria.objects.filter(pergunta__in=perguntas, registro__in=registros_qs)
        .select_related("registro", "pergunta")
        .order_by("registro__data_auditoria", "id")
    )

    respostas_por_pergunta: dict[int, list[RespostaAuditoria]] = {}
    for r in respostas_qs:
        respostas_por_pergunta.setdefault(r.pergunta_id, []).append(r)

    def _normalize_sim_nao(value: str) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if raw in {"True", "true", "Sim", "sim", "1", "SIM"}:
            return "Sim"
        if raw in {"False", "false", "Não", "não", "Nao", "nao", "0", "NAO", "NÃO"}:
            return "Não"
        return raw

    def _short(text: str, limit: int = 42) -> str:
        raw = (text or "").strip()
        if len(raw) <= limit:
            return raw
        return raw[: max(0, limit - 3)].rstrip() + "..."

    # Estatísticas (tabela) e dados dos gráficos por tipo/pergunta
    estatisticas_perguntas: list[dict] = []
    chart_cards: list[dict] = []
    chart_data: dict[str, dict] = {}

    tipo_cards_def = [
        {"tipo": "SIM_NAO", "key": "sim_nao", "label": "Sim/Não"},
        {"tipo": "LISTA", "key": "lista", "label": "Lista (opções)"},
        {"tipo": "NUMERO", "key": "numero", "label": "Número inteiro"},
        {"tipo": "DECIMAL", "key": "decimal", "label": "Número decimal"},
    ]

    perguntas_por_tipo: dict[str, list[PerguntaAuditoria]] = {d["tipo"]: [] for d in tipo_cards_def}
    for p in perguntas:
        if p.tipo_resposta in perguntas_por_tipo:
            perguntas_por_tipo[p.tipo_resposta].append(p)

    for d in tipo_cards_def:
        tipo = d["tipo"]
        key = d["key"]
        label = d["label"]
        perguntas_tipo = perguntas_por_tipo.get(tipo) or []
        if not perguntas_tipo:
            continue

        chart_cards.append({
            "key": key,
            "label": label,
            "tipo": tipo,
            "perguntas": ([{"id": "__all__", "texto": "Todas"}] + [{"id": p.id, "texto": p.pergunta} for p in perguntas_tipo]),
        })
        chart_data[key] = {"tipo": tipo, "perguntas": {}}

        # Agregado (todas as perguntas do tipo)
        all_respostas: list[RespostaAuditoria] = []
        for p in perguntas_tipo:
            all_respostas.extend(respostas_por_pergunta.get(p.id, []))

        if tipo == "SIM_NAO":
            # Geral por pergunta (barras empilhadas)
            labels_q = [_short(p.pergunta) for p in perguntas_tipo]
            sim_by_q: list[int] = []
            nao_by_q: list[int] = []
            for p in perguntas_tipo:
                respostas_p = respostas_por_pergunta.get(p.id, [])
                sim_count = 0
                nao_count = 0
                for r in respostas_p:
                    val = _normalize_sim_nao(r.valor)
                    if val == "Sim":
                        sim_count += 1
                    elif val == "Não":
                        nao_count += 1
                sim_by_q.append(sim_count)
                nao_by_q.append(nao_count)

            por_data: dict[str, dict[str, int]] = {}
            for r in all_respostas:
                val = _normalize_sim_nao(r.valor)
                if val not in {"Sim", "Não"}:
                    continue
                date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                if not date_key:
                    continue
                por_data.setdefault(date_key, {"Sim": 0, "Não": 0})
                por_data[date_key][val] += 1

            labels_date = sorted(por_data.keys())
            chart_data[key]["perguntas"]["__all__"] = {
                "current": {
                    "labels": labels_q,
                    "datasets": [
                        {"label": "Sim", "data": sim_by_q},
                        {"label": "Não", "data": nao_by_q},
                    ],
                },
                "by_date": {
                    "labels": labels_date,
                    "datasets": [
                        {"label": "Sim", "data": [por_data[d]["Sim"] for d in labels_date]},
                        {"label": "Não", "data": [por_data[d]["Não"] for d in labels_date]},
                    ],
                },
            }

        elif tipo == "LISTA":
            # Geral por pergunta: total de respostas por pergunta (uma barra por pergunta)
            labels_q = [_short(p.pergunta) for p in perguntas_tipo]
            total_by_q: list[int] = []
            for p in perguntas_tipo:
                respostas_p = respostas_por_pergunta.get(p.id, [])
                count = 0
                for r in respostas_p:
                    opt = (str(r.valor).strip() if r.valor is not None else "")
                    if opt:
                        count += 1
                total_by_q.append(count)

            counts: dict[str, int] = {}
            por_data_opt: dict[str, dict[str, int]] = {}
            for r in all_respostas:
                opt = (str(r.valor).strip() if r.valor is not None else "")
                if not opt:
                    continue
                counts[opt] = counts.get(opt, 0) + 1
                date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                if not date_key:
                    continue
                por_data_opt.setdefault(date_key, {})
                por_data_opt[date_key][opt] = por_data_opt[date_key].get(opt, 0) + 1

            options_sorted = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
            opt_labels = [k for (k, _v) in options_sorted]
            labels_date = sorted(por_data_opt.keys())

            datasets = []
            for opt in opt_labels:
                datasets.append({
                    "label": opt,
                    "data": [por_data_opt.get(d, {}).get(opt, 0) for d in labels_date],
                })

            chart_data[key]["perguntas"]["__all__"] = {
                "current": {
                    "labels": labels_q,
                    "datasets": [
                        {"label": "Respostas", "data": total_by_q},
                    ],
                },
                "by_date": {"labels": labels_date, "datasets": datasets},
            }

        elif tipo in {"NUMERO", "DECIMAL"}:
            # Geral por pergunta (apenas Valor por pergunta)
            labels_q = [_short(p.pergunta) for p in perguntas_tipo]
            avgs_q: list[float | None] = []
            for p in perguntas_tipo:
                vals: list[float] = []
                for r in respostas_por_pergunta.get(p.id, []):
                    raw = (r.valor or "").strip() if isinstance(r.valor, str) else ("" if r.valor is None else str(r.valor))
                    if not raw:
                        continue
                    try:
                        vals.append(float(raw.replace(",", ".")))
                    except (ValueError, TypeError):
                        continue
                if vals:
                    avgs_q.append(sum(vals) / len(vals))
                else:
                    avgs_q.append(None)

            # Por data (todas): uma série por pergunta (média por dia, se houver múltiplos registros)
            values_by_q_by_date: dict[int, dict[str, list[float]]] = {}
            all_dates: set[str] = set()
            for p in perguntas_tipo:
                for r in respostas_por_pergunta.get(p.id, []):
                    raw = (r.valor or "").strip() if isinstance(r.valor, str) else ("" if r.valor is None else str(r.valor))
                    if not raw:
                        continue
                    try:
                        num = float(raw.replace(",", "."))
                    except (ValueError, TypeError):
                        continue
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    all_dates.add(date_key)
                    values_by_q_by_date.setdefault(p.id, {}).setdefault(date_key, []).append(num)

            labels_date = sorted(all_dates)
            datasets_by_date: list[dict] = []
            for p in perguntas_tipo:
                per_date = values_by_q_by_date.get(p.id, {})
                data_points: list[float | None] = []
                for dte in labels_date:
                    arr = per_date.get(dte) or []
                    data_points.append((sum(arr) / len(arr)) if arr else None)
                datasets_by_date.append({"label": _short(p.pergunta), "data": data_points})

            chart_data[key]["perguntas"]["__all__"] = {
                "current": {
                    "labels": labels_q,
                    "datasets": [
                        {"label": "Valor", "data": avgs_q},
                    ],
                },
                "by_date": {"labels": labels_date, "datasets": datasets_by_date},
            }

        for pergunta in perguntas_tipo:
            respostas = respostas_por_pergunta.get(pergunta.id, [])
            total_respostas = len(respostas)
            estatistica = {
                "pergunta": pergunta.pergunta,
                "tipo": pergunta.get_tipo_resposta_display(),
                "total_respostas": total_respostas,
            }

            if pergunta.tipo_resposta == "SIM_NAO":
                sim_total = 0
                nao_total = 0
                por_data: dict[str, dict[str, int]] = {}
                for r in respostas:
                    val = _normalize_sim_nao(r.valor)
                    if val not in {"Sim", "Não"}:
                        continue
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    por_data.setdefault(date_key, {"Sim": 0, "Não": 0})
                    por_data[date_key][val] += 1
                    if val == "Sim":
                        sim_total += 1
                    else:
                        nao_total += 1

                estatistica["sim"] = sim_total
                estatistica["nao"] = nao_total

                labels_date = sorted(por_data.keys())
                chart_data[key]["perguntas"][str(pergunta.id)] = {
                    "current": {"labels": ["Sim", "Não"], "values": [sim_total, nao_total]},
                    "by_date": {
                        "labels": labels_date,
                        "datasets": [
                            {"label": "Sim", "data": [por_data[d]["Sim"] for d in labels_date]},
                            {"label": "Não", "data": [por_data[d]["Não"] for d in labels_date]},
                        ],
                    },
                }

            elif pergunta.tipo_resposta == "LISTA":
                counts: dict[str, int] = {}
                por_data_opt: dict[str, dict[str, int]] = {}
                for r in respostas:
                    opt = (str(r.valor).strip() if r.valor is not None else "")
                    if not opt:
                        continue
                    counts[opt] = counts.get(opt, 0) + 1
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    por_data_opt.setdefault(date_key, {})
                    por_data_opt[date_key][opt] = por_data_opt[date_key].get(opt, 0) + 1

                options_sorted = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
                opt_labels = [k for (k, _v) in options_sorted]
                opt_values = [v for (_k, v) in options_sorted]
                labels_date = sorted(por_data_opt.keys())

                datasets = []
                for opt in opt_labels:
                    datasets.append({
                        "label": opt,
                        "data": [por_data_opt.get(d, {}).get(opt, 0) for d in labels_date],
                    })

                chart_data[key]["perguntas"][str(pergunta.id)] = {
                    "current": {"labels": opt_labels, "values": opt_values},
                    "by_date": {"labels": labels_date, "datasets": datasets},
                }

            elif pergunta.tipo_resposta in {"NUMERO", "DECIMAL"}:
                values: list[float] = []
                por_data_vals: dict[str, list[float]] = {}
                for r in respostas:
                    raw = (r.valor or "").strip() if isinstance(r.valor, str) else ("" if r.valor is None else str(r.valor))
                    if not raw:
                        continue
                    try:
                        num = float(raw.replace(",", "."))
                    except (ValueError, TypeError):
                        continue
                    values.append(num)
                    date_key = r.registro.data_auditoria.strftime("%Y-%m-%d") if r.registro.data_auditoria else ""
                    if not date_key:
                        continue
                    por_data_vals.setdefault(date_key, []).append(num)

                if values:
                    avg_v = sum(values) / len(values)
                    estatistica["media"] = round(avg_v, 2)
                else:
                    avg_v = None

                labels_date = sorted(por_data_vals.keys())
                avg_by_date = []
                for dte in labels_date:
                    arr = por_data_vals.get(dte) or []
                    avg_by_date.append((sum(arr) / len(arr)) if arr else None)

                chart_data[key]["perguntas"][str(pergunta.id)] = {
                    "current": {
                        "labels": ["Valor"],
                        "values": [avg_v],
                    },
                    "by_date": {
                        "labels": labels_date,
                        "datasets": [
                            {"label": pergunta.pergunta, "data": avg_by_date},
                        ],
                    },
                }

            estatisticas_perguntas.append(estatistica)

    context = {
        "modelo": modelo,
        "page_obj": page_obj,
        "paginator": paginator,
        "querystring_base": querystring_base,
        "querystring_with_page": querystring_with_page,
        "per_page": per_page,
        "per_page_options": sorted(allowed_per_page),
        "registros_count": paginator.count,
        "comentarios": comentarios,
        "is_insumos_admin": _auditoria_is_admin(request.user),
        "perguntas": perguntas,
        "estatisticas_perguntas": estatisticas_perguntas,
        "chart_cards": chart_cards,
        "chart_data": chart_data,
        "inicio": inicio_raw,
        "fim": fim_raw,
    }
    return render(request, "insumos/registros_por_modelo.html", context)


@login_required
def comentario_edit(request, modelo_id, pk):
    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )
    comentario = get_object_or_404(ComentarioInsumos, pk=pk, modelo=modelo)
    can_manage = _auditoria_is_admin(request.user) or (comentario.autor_id == request.user.id)

    preserved = {}
    for k in ("inicio", "fim", "page", "per_page"):
        v = (request.GET.get(k) or "").strip()
        if v:
            preserved[k] = v
    back_url = reverse("insumos:registros_por_modelo", args=[modelo.id])
    if preserved:
        back_url = f"{back_url}?{urlencode(preserved)}"

    if not can_manage:
        messages.error(request, "Você não tem permissão para editar este comentário.")
        return redirect(back_url)

    if request.method == "POST":
        form = ComentarioInsumosForm(request.POST, instance=comentario)
        if form.is_valid():
            form.save()
            messages.success(request, "Comentário atualizado com sucesso.")
            return redirect(back_url)
    else:
        form = ComentarioInsumosForm(instance=comentario)

    return render(
        request,
        "insumos/comentario_form.html",
        {
            "modelo": modelo,
            "comentario": comentario,
            "form": form,
            "back_url": back_url,
        },
    )


@login_required
def comentario_delete(request, modelo_id, pk):
    modelo = get_object_or_404(
        _filter_modelos_para_usuario(request.user, ModeloAuditoria.objects.all()),
        pk=modelo_id,
    )
    comentario = get_object_or_404(ComentarioInsumos, pk=pk, modelo=modelo)
    can_manage = _auditoria_is_admin(request.user) or (comentario.autor_id == request.user.id)

    preserved = {}
    for k in ("inicio", "fim", "page", "per_page"):
        v = (request.GET.get(k) or "").strip()
        if v:
            preserved[k] = v
    back_url = reverse("insumos:registros_por_modelo", args=[modelo.id])
    if preserved:
        back_url = f"{back_url}?{urlencode(preserved)}"

    if not can_manage:
        messages.error(request, "Você não tem permissão para remover este comentário.")
        return redirect(back_url)

    if request.method == "POST":
        comentario.delete()
        messages.success(request, "Comentário removido com sucesso.")
        return redirect(back_url)

    return render(
        request,
        "insumos/comentario_confirm_delete.html",
        {
            "modelo": modelo,
            "comentario": comentario,
            "back_url": back_url,
        },
    )


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
        "Data",
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

