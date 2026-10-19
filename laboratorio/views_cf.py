"""Telas do Retrabalho CF (HMC > Controle Final): dashboard, registros, formulário, configurações e importação."""
import calendar
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from maquinas.models import Maquina
from rh.models import Colaborador

from . import cf_importacao as imp
from . import cf_retrabalho as cf
from . import planilhas
from .models import (
    CFCadastro,
    CFCampoFormulario,
    EquipeCF,
    RegraTurnoCoating,
    RetrabalhoCFConfig,
    RetrabalhoCFItem,
    RetrabalhoCFRegistro,
    TratamentoAntiReflexo,
)
from .views_hc import MAX_UPLOAD, _data, _inteiro, _periodo

ABAS_DASHBOARD = [
    ("geral", "Geral", "bi-table"),
    ("motivo", "Retrabalho x Motivo", "bi-exclamation-triangle"),
    ("maquina", "Retrabalho x Máquina", "bi-gear"),
    ("tratamento", "Retrabalho x Tratamento", "bi-droplet-half"),
    ("colaborador", "Colaboradores", "bi-person"),
    ("cxt", "Colaborador x Tratamento", "bi-grid-3x3"),
]


def _mes_referencia():
    ultimo = RetrabalhoCFRegistro.objects.order_by("-data").values_list("data", flat=True).first() or date.today()
    ini = ultimo.replace(day=1)
    return ini, ini.replace(day=calendar.monthrange(ini.year, ini.month)[1])


def _grafico(aba, dados):
    if not dados:
        return None
    meta = dados.get("meta")
    if aba == "geral":
        l = dados["linhas"]
        return {"tipo": "line", "meta": meta, "labels": [x["data"].strftime("%d/%m") for x in l], "datasets": [
            {"label": "% Retrabalho", "data": [x["pct_ret"] for x in l]},
            {"label": "% Lentes reprovadas", "data": [x["pct_lentes_rep"] for x in l]}]}
    if aba == "motivo":
        l = [x for g in dados["grupos"] for x in g["linhas"] if x["total"]]
        return {"tipo": "bar", "labels": [x["nome"] for x in l], "datasets": [{"label": "Retrabalho (peças)", "data": [x["total"] for x in l]}]}
    if aba in ("maquina", "tratamento", "colaborador") and dados.get("linhas"):
        l = dados["linhas"]
        return {"tipo": "line", "meta": meta, "labels": [x["data"].strftime("%d/%m") for x in l],
                "datasets": [{"label": "% Retrabalho", "data": [x["pct_ret"] for x in l]}]}
    return None


@login_required
def cf_dashboard(request):
    cf.garantir_padroes()
    aba = request.GET.get("aba", "geral")
    if aba not in {a[0] for a in ABAS_DASHBOARD}:
        aba = "geral"
    mes_ini, mes_fim = _mes_referencia()
    inicio, fim = _periodo(request, mes_ini, mes_fim)
    papel = "ar" if request.GET.get("papel") == "ar" else "cf"
    ctx = {"abas": ABAS_DASHBOARD, "aba": aba, "inicio": inicio, "fim": fim, "meta": cf.meta(), "papel": papel,
           "total_registros": RetrabalhoCFRegistro.objects.count()}
    if aba == "motivo":
        ctx["dados"] = cf.retrabalho_motivo(inicio, fim)
    elif aba in ("maquina", "tratamento"):
        sel = request.GET.get("item", "")
        ctx.update(opcoes=cf.opcoes_dimensao(aba), item_sel=sel, dados=cf.analise_dimensao(aba, sel, inicio, fim))
    elif aba == "colaborador":
        chave = request.GET.get("colaborador", "")
        ctx.update(colaboradores=cf.lista_colaboradores(papel), colaborador_sel=chave, dados=cf.analise_colaborador(papel, chave, inicio, fim))
    elif aba == "cxt":
        ctx["dados"] = cf.colaborador_x_tratamento(papel, inicio, fim)
    else:
        ctx["dados"] = cf.geral(inicio, fim)
    ctx["grafico"] = _grafico(aba, ctx.get("dados"))
    return render(request, "laboratorio/cf_dashboard.html", ctx)


@login_required
def cf_dia_hora(request):
    """Retrabalho CF de um dia, hora a hora (hora = hora do lançamento no formulário)."""
    cf.garantir_padroes()
    ultimo = RetrabalhoCFRegistro.objects.order_by("-data").values_list("data", flat=True).first() or date.today()
    dia = _data(request.GET.get("data"), ultimo)
    dados = cf.por_hora(dia)
    linhas = dados["linhas"]
    grafico = {"tipo": "line", "meta": dados["meta"], "labels": [l["rotulo"] for l in linhas], "datasets": [
        {"label": "% Retrabalho", "data": [l["pct_ret"] for l in linhas]},
        {"label": "% Lentes reprovadas", "data": [l["pct_lentes_rep"] for l in linhas]}]} if linhas else None
    return render(request, "laboratorio/cf_dia_hora.html", {"dia": dia, "dados": dados, "meta": dados["meta"], "grafico": grafico})


# --------------------------------------------------------------------------- registros
def _filtrar_registros(request):
    qs = RetrabalhoCFRegistro.objects.select_related("colaborador_cf", "colaborador_ar", "turno", "maquina", "tratamento")
    ini, fim = _data(request.GET.get("inicio"), None), _data(request.GET.get("fim"), None)
    if ini:
        qs = qs.filter(data__gte=ini)
    if fim:
        qs = qs.filter(data__lte=fim)
    turno = _inteiro(request.GET.get("turno"))
    if turno:
        qs = qs.filter(turno_id=turno)
    busca = (request.GET.get("q") or "").strip()
    if busca:
        qs = qs.filter(Q(numero_lote__icontains=busca) | Q(colaborador_cf__nome_completo__icontains=busca) | Q(colaborador_cf_nome__icontains=busca)
                       | Q(maquina_nome__icontains=busca) | Q(tratamento_nome__icontains=busca))
    return qs, turno, busca


@login_required
def cf_registros(request):
    qs, turno, busca = _filtrar_registros(request)
    pagina = Paginator(qs, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "laboratorio/cf_registros.html", {
        "pagina": pagina, "turnos": RegraTurnoCoating.objects.filter(ativo=True), "inicio": request.GET.get("inicio", ""),
        "fim": request.GET.get("fim", ""), "turno_sel": turno, "q": busca, "querystring": params.urlencode()})


@login_required
def cf_registro_detalhe(request, pk):
    """Conteúdo do pop-up de um lote (somente leitura, com editar/excluir)."""
    r = get_object_or_404(RetrabalhoCFRegistro.objects.select_related("colaborador_cf", "colaborador_ar", "usuario"), pk=pk)
    rot = {c.chave: c.rotulo for c in CFCampoFormulario.objects.all()}
    sim_nao = lambda v: "Sim" if v else "Não"
    campos = [
        (rot.get("data", "Data"), r.data.strftime("%d/%m/%Y") + (r.hora.strftime(" %H:%M") if r.hora else "")), (rot.get("turno", "Turno"), r.turno_nome or "–"),
        (rot.get("numero_lote", "Número do Lote"), r.numero_lote or "–"), (rot.get("total_lentes", "Total de Lentes no Lote"), r.total_lentes),
        (rot.get("maquina", "Máquina"), r.maquina_nome or "–"), (rot.get("tratamento", "Tratamento"), r.tratamento_nome or "–"),
        (rot.get("colaborador_cf", "Colaborador CF"), r.colaborador_cf_display or "–"), (rot.get("colaborador_ar", "Colaborador AR"), r.colaborador_ar_display or "–"),
        (rot.get("necessidade_retrabalho", "Necessidade de Retrabalho?"), sim_nao(r.teve_retrabalho)),
        ("Total retrabalhado", f"{r.qtd_retrabalho} ({r.qtd_retrabalho * 100 // r.total_lentes}%)" if r.total_lentes else r.qtd_retrabalho),
        (rot.get("lote_reprovado", "Lote Reprovado?"), sim_nao(r.reprovado)),
    ]
    if r.reprovado:
        campos.append((rot.get("motivo_reprovacao", "Motivo da Reprovação"), r.motivo_reprovacao or "–"))
    itens = list(r.itens.select_related("motivo").order_by("motivo__grupo", "motivo__ordem"))
    grupos = []
    for origem, nome in CFCadastro.ORIGEM_CHOICES:
        linhas = [(i.motivo.nome, i.quantidade) for i in itens if i.motivo.grupo == origem]
        if linhas:
            grupos.append({"titulo": f"Retrabalho — {nome}", "linhas": linhas, "total": sum(q for _n, q in linhas)})
    extras = [(rot.get(k, k), v) for k, v in (r.extras or {}).items() if v not in (None, "")]
    return render(request, "laboratorio/_cf_registro_detalhe.html", {"r": r, "campos": campos, "grupos": grupos, "extras": extras})


@login_required
def cf_registro_create(request):
    form = cf.RegistroCFForm(request.POST or None, initial={"data": timezone.localtime().replace(second=0, microsecond=0, tzinfo=None)})
    if request.method == "POST" and form.is_valid():
        r = form.save(usuario=request.user)
        messages.success(request, f"Lote registrado: {r.total_lentes} lentes, {r.qtd_retrabalho} retrabalho(s).")
        return redirect("laboratorio:cf_registro_create" if "salvar_novo" in request.POST else "laboratorio:cf_registros")
    return render(request, "laboratorio/cf_registro_form.html", {"form": form, "titulo": "Novo lançamento de retrabalho"})


@login_required
def cf_registro_update(request, pk):
    registro = get_object_or_404(RetrabalhoCFRegistro, pk=pk)
    form = cf.RegistroCFForm(request.POST or None, instance=registro)
    if request.method == "POST" and form.is_valid():
        form.save(usuario=request.user)
        messages.success(request, "Lançamento atualizado.")
        return redirect("laboratorio:cf_registros")
    return render(request, "laboratorio/cf_registro_form.html", {"form": form, "titulo": "Editar lançamento", "registro": registro})


@login_required
@require_POST
def cf_registro_delete(request, pk):
    get_object_or_404(RetrabalhoCFRegistro, pk=pk).delete()
    messages.success(request, "Lançamento excluído.")
    return redirect("laboratorio:cf_registros")


# --------------------------------------------------------------------------- configurações: campos
@login_required
def cf_config_campos(request):
    cf.garantir_padroes()
    return render(request, "laboratorio/cf_config_campos.html", {
        "campos": CFCampoFormulario.objects.all(), "tipos": CFCampoFormulario.TIPO_CHOICES, "config": RetrabalhoCFConfig.get()})


@login_required
@require_POST
def cf_campo_save(request):
    pk = _inteiro(request.POST.get("id"))
    rotulo = (request.POST.get("rotulo") or "").strip()
    if not rotulo:
        messages.error(request, "Informe a pergunta/rótulo do campo.")
        return redirect("laboratorio:cf_config_campos")
    if pk:
        campo = get_object_or_404(CFCampoFormulario, pk=pk)
    else:
        base = slugify(rotulo)[:40] or "campo"
        chave, i = base, 2
        while CFCampoFormulario.objects.filter(chave=chave).exists():
            chave, i = f"{base}-{i}", i + 1
        ultimo = CFCampoFormulario.objects.order_by("-ordem").first()
        campo = CFCampoFormulario(chave=chave, ordem=(ultimo.ordem + 10) if ultimo else 0)
    campo.rotulo = rotulo[:200]
    campo.ajuda = (request.POST.get("ajuda") or "").strip()[:255]
    campo.obrigatorio = request.POST.get("obrigatorio") == "on"
    campo.visivel = request.POST.get("visivel") == "on" or campo.chave in CFCampoFormulario.CHAVES_OBRIGATORIAS
    if not campo.sistema:
        tipo = request.POST.get("tipo")
        campo.tipo = tipo if tipo in dict(CFCampoFormulario.TIPO_CHOICES) else "TEXTO"
        campo.opcoes = (request.POST.get("opcoes") or "").strip()
        if campo.tipo == "SELECAO" and not campo.lista_opcoes:
            messages.error(request, "Informe ao menos uma opção para o campo de lista suspensa.")
            return redirect("laboratorio:cf_config_campos")
    campo.save()
    messages.success(request, f"Campo '{campo.rotulo}' salvo.")
    return redirect("laboratorio:cf_config_campos")


@login_required
@require_POST
def cf_campo_mover(request, pk):
    campos = list(CFCampoFormulario.objects.all())
    idx = next((i for i, c in enumerate(campos) if c.pk == pk), None)
    if idx is not None:
        destino = idx - 1 if request.POST.get("direcao") == "up" else idx + 1
        if 0 <= destino < len(campos):
            campos[idx], campos[destino] = campos[destino], campos[idx]
            for i, c in enumerate(campos):
                if c.ordem != i * 10:
                    CFCampoFormulario.objects.filter(pk=c.pk).update(ordem=i * 10)
    return redirect("laboratorio:cf_config_campos")


@login_required
@require_POST
def cf_campo_delete(request, pk):
    campo = get_object_or_404(CFCampoFormulario, pk=pk)
    if campo.sistema:
        messages.error(request, "Campos de sistema não podem ser excluídos; oculte-o se não for necessário.")
    else:
        campo.delete()
        messages.success(request, f"Campo '{campo.rotulo}' excluído (respostas já lançadas continuam guardadas).")
    return redirect("laboratorio:cf_config_campos")


@login_required
@require_POST
def cf_config_meta(request):
    try:
        valor = Decimal((request.POST.get("meta_retrabalho") or "").replace(",", "."))
    except InvalidOperation:
        valor = None
    if valor is None or not (0 < valor <= 100):
        messages.error(request, "Meta inválida: informe um percentual entre 0 e 100.")
    else:
        config = RetrabalhoCFConfig.get()
        config.meta_retrabalho = valor
        config.save()
        messages.success(request, f"Meta máxima de retrabalho atualizada para {valor}%.")
    return redirect("laboratorio:cf_config_campos")


# --------------------------------------------------------------------------- configurações: cadastros
@login_required
def cf_config_cadastros(request):
    cf.garantir_padroes()
    aba = request.GET.get("aba", "MOTIVO")
    if aba not in ("MOTIVO", "REPROVACAO", "EQUIPE"):
        aba = "MOTIVO"
    ctx = {"aba": aba, "origens": CFCadastro.ORIGEM_CHOICES}
    if aba == "EQUIPE":
        ctx["equipe"] = EquipeCF.objects.select_related("colaborador")
        ctx["disponiveis"] = Colaborador.objects.filter(is_active=True).exclude(pk__in=ctx["equipe"].values_list("colaborador_id", flat=True)).order_by("nome_completo")
    elif aba == "MOTIVO":
        ctx["grupos"] = [(o, n, CFCadastro.objects.filter(tipo="MOTIVO", grupo=o)) for o, n in CFCadastro.ORIGEM_CHOICES]
    else:
        ctx["itens"] = CFCadastro.objects.filter(tipo="REPROVACAO")
    return render(request, "laboratorio/cf_config_cadastros.html", ctx)


def _volta(aba):
    return redirect(f"{reverse('laboratorio:cf_config_cadastros')}?aba={aba}")


@login_required
@require_POST
def cf_cadastro_save(request):
    tipo = request.POST.get("tipo")
    nome = (request.POST.get("nome") or "").strip()
    if tipo not in ("MOTIVO", "REPROVACAO"):
        return redirect("laboratorio:cf_config_cadastros")
    if not nome:
        messages.error(request, "Informe o nome.")
        return _volta(tipo)
    pk = _inteiro(request.POST.get("id"))
    item = get_object_or_404(CFCadastro, pk=pk, tipo=tipo) if pk else CFCadastro(tipo=tipo)
    grupo = request.POST.get("grupo") if tipo == "MOTIVO" else ""
    if tipo == "MOTIVO" and grupo not in dict(CFCadastro.ORIGEM_CHOICES):
        grupo = item.grupo or "CF"
    if pk:
        grupo = item.grupo  # a origem não muda depois de criada (preserva o histórico)
    if CFCadastro.objects.filter(tipo=tipo, grupo=grupo, nome__iexact=nome).exclude(pk=item.pk).exists():
        messages.error(request, f"Já existe '{nome}' neste cadastro.")
        return _volta(tipo)
    item.nome, item.grupo = nome[:150], grupo
    ordem = _inteiro(request.POST.get("ordem"))
    if ordem is None:
        ultimo = CFCadastro.objects.filter(tipo=tipo, grupo=grupo).order_by("-ordem").first()
        ordem = (ultimo.ordem + 1) if ultimo else 0
    item.ordem = max(ordem, 0)
    item.ativo = (request.POST.get("ativo") == "on") if pk else True
    item.save()
    messages.success(request, f"'{item.nome}' salvo.")
    return _volta(tipo)


@login_required
@require_POST
def cf_cadastro_delete(request, pk):
    item = get_object_or_404(CFCadastro, pk=pk)
    em_uso = (RetrabalhoCFItem.objects.filter(motivo=item).exists() if item.tipo == "MOTIVO"
              else RetrabalhoCFRegistro.objects.filter(motivo_reprovacao=item.nome).exists())
    if em_uso:
        item.ativo = False
        item.save(update_fields=["ativo"])
        messages.warning(request, f"'{item.nome}' já tem lançamentos; foi inativado em vez de excluído.")
    else:
        item.delete()
        messages.success(request, f"'{item.nome}' excluído.")
    return _volta(item.tipo)


@login_required
@require_POST
def cf_equipe_save(request):
    pk = _inteiro(request.POST.get("id"))
    if pk:
        membro = get_object_or_404(EquipeCF, pk=pk)
        membro.apelidos = (request.POST.get("apelidos") or "").strip()[:255]
        membro.ativo = request.POST.get("ativo") == "on"
        membro.save()
        messages.success(request, f"{membro.colaborador.nome_completo} atualizado.")
    else:
        colab = get_object_or_404(Colaborador, pk=_inteiro(request.POST.get("colaborador"), 0))
        EquipeCF.objects.get_or_create(colaborador=colab, defaults={"apelidos": (request.POST.get("apelidos") or "").strip()[:255]})
        messages.success(request, f"{colab.nome_completo} adicionado à Equipe Controle Final.")
    return _volta("EQUIPE")


@login_required
@require_POST
def cf_equipe_delete(request, pk):
    membro = get_object_or_404(EquipeCF, pk=pk)
    membro.delete()
    messages.success(request, f"{membro.colaborador.nome_completo} removido da Equipe Controle Final.")
    return _volta("EQUIPE")


# --------------------------------------------------------------------------- integrações
@login_required
def cf_config_integracoes(request):
    cf.garantir_padroes()
    p = cf.propostas_sincronizacao()
    return render(request, "laboratorio/cf_config_integracoes.html", {
        "propostas": p, "turnos": RegraTurnoCoating.objects.count(), "tratamentos": TratamentoAntiReflexo.objects.count(),
        "maquinas": cf.maquinas_cf().count(), "montagem": cf.colaboradores_montagem().count(),
        "colaboradores": Colaborador.objects.filter(is_active=True).order_by("nome_completo"),
        "lista_maquinas": Maquina.objects.order_by("codigo"), "lista_tratamentos": TratamentoAntiReflexo.objects.order_by("nome"),
        "pendencias": sum(len(v["itens"]) for v in p["vinculos"].values())})


@login_required
@require_POST
def cf_sincronizar(request):
    novos, desativados = cf.aplicar_sincronizacao()
    messages.success(request, f"Sincronização concluída: {novos} adicionado(s) e {desativados} desativado(s) na Equipe Controle Final.")
    return redirect("laboratorio:cf_config_integracoes")


@login_required
@require_POST
def cf_vincular(request):
    """Vincula um nome digitado nos lançamentos antigos ao cadastro oficial (colaborador, máquina ou tratamento)."""
    chave = request.POST.get("chave", "")  # colab_cf | colab_ar | maquina | tratamento
    nome = request.POST.get("nome", "")
    objeto = _inteiro(request.POST.get("objeto"), 0)
    modelo = {"colab_cf": Colaborador, "colab_ar": Colaborador, "maquina": Maquina, "tratamento": TratamentoAntiReflexo}.get(chave)
    if not modelo or not modelo.objects.filter(pk=objeto).exists():
        messages.error(request, "Selecione o cadastro de destino.")
        return redirect("laboratorio:cf_config_integracoes")
    tipo, papel = ("colaborador", chave[-2:]) if chave.startswith("colab") else (chave, "")
    n = cf.vincular(tipo, papel, nome, objeto)
    messages.success(request, f"{n} lançamento(s) de '{nome}' vinculados.")
    return redirect("laboratorio:cf_config_integracoes")


@login_required
@require_POST
def cf_criar_tratamento(request):
    """Cria o tratamento no cadastro do Anti-Reflexo e vincula os lançamentos com esse nome."""
    nome = (request.POST.get("nome") or "").strip()
    if nome:
        t, criado = TratamentoAntiReflexo.objects.get_or_create(nome=nome)
        n = cf.vincular("tratamento", "", nome, t.pk)
        messages.success(request, f"Tratamento '{t.nome}' {'criado e ' if criado else ''}vinculado a {n} lançamento(s).")
    return redirect("laboratorio:cf_config_integracoes")


# --------------------------------------------------------------------------- importação
def _ler_upload(request):
    arquivo = request.FILES.get("arquivo")
    if not arquivo:
        raise ValueError("Selecione a planilha (.xlsx ou .csv).")
    if arquivo.size > MAX_UPLOAD:
        raise ValueError("Arquivo maior que 15 MB.")
    if not arquivo.name.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise ValueError("Formato não suportado: use .xlsx ou .csv.")
    return imp.ler_planilha(arquivo, request.POST.get("aba") or None)


@login_required
def cf_importar(request):
    cf.garantir_padroes()
    resultado = None
    if request.method == "POST":
        try:
            dados = _ler_upload(request)
            mapa = {k[4:]: v for k, v in request.POST.items() if k.startswith("map_") and v != ""}
            resultado = imp.importar(dados["linhas"], mapa, a_partir=_data(request.POST.get("a_partir"), None),
                                     simular=request.POST.get("acao") == "simular", usuario=request.user)
            if resultado["simulado"]:
                messages.info(request, f"Simulação: {resultado['validas']} lançamento(s) seriam importados. Nada foi gravado.")
            else:
                messages.success(request, f"{resultado['importadas']} lançamento(s) importados.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "laboratorio/cf_importar.html", {"alvos": imp.alvos(), "resultado": resultado})


@login_required
@require_POST
def cf_importar_preview(request):
    try:
        dados = _ler_upload(request)
    except ValueError as exc:
        return JsonResponse({"erro": str(exc)}, status=400)
    amostra = [["" if v is None else str(v)[:40] for v in linha] for linha in dados["linhas"][:2]]
    return JsonResponse({"abas": dados["abas"], "aba": dados["aba"], "cabecalhos": dados["cabecalhos"], "total": len(dados["linhas"]),
                         "sugestao": imp.sugerir_mapa(dados["cabecalhos"]), "amostra": amostra})


# --------------------------------------------------------------------------- modelo e exportação
@login_required
def cf_modelo(request):
    return planilhas.modelo("cf")


@login_required
def cf_exportar(request):
    qs, _turno, _busca = _filtrar_registros(request)
    return planilhas.exportar("cf", qs)
