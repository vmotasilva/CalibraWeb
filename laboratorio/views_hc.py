"""Telas do Rendimento HC (HMC > HC): dashboard, registros, formulário e configurações."""
import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from rh.models import Colaborador

from . import hc_importacao as imp
from . import hc_rendimento as hc
from .models import (
    EquipeHC,
    HCCadastro,
    HCCampoFormulario,
    RegraTurnoCoating,
    RendimentoHCConfig,
    RendimentoHCItem,
    RendimentoHCRegistro,
    TratamentoAntiReflexo,
)

ABAS_DASHBOARD = [
    ("consolidado", "Consolidado", "bi-table"),
    ("diaria", "Análise Diária", "bi-calendar-day"),
    ("motivo", "Retrabalho x Motivo", "bi-exclamation-triangle"),
    ("colaborador", "Colaborador", "bi-person"),
    ("ano", "Retrabalho x Ano", "bi-calendar3"),
    ("material", "Rendimento por Material", "bi-layers"),
]
MAX_DIAS = 366


def _data(valor, padrao):
    try:
        return date.fromisoformat((valor or "").strip())
    except ValueError:
        return padrao


def _inteiro(valor, padrao=None):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def _periodo(request, padrao_ini, padrao_fim):
    ini = _data(request.GET.get("inicio"), padrao_ini)
    fim = _data(request.GET.get("fim"), padrao_fim)
    if fim < ini:
        ini, fim = fim, ini
    if (fim - ini).days > MAX_DIAS:
        fim = ini + timedelta(days=MAX_DIAS)
    return ini, fim


def _mes_referencia():
    """Mês do último lançamento (ou o mês atual, se ainda não há dados)."""
    ultimo = RendimentoHCRegistro.objects.order_by("-data").values_list("data", flat=True).first() or date.today()
    ini = ultimo.replace(day=1)
    return ini, ini.replace(day=calendar.monthrange(ini.year, ini.month)[1]), ultimo


# --------------------------------------------------------------------------- dashboard
def _grafico(aba, dados):
    """Dados do Chart.js da aba (None quando não há o que desenhar)."""
    if not dados:
        return None
    meta = dados.get("meta")
    if aba == "consolidado":
        linhas = dados["linhas"]
        return {"tipo": "line", "meta": meta, "labels": [l["data"].strftime("%d/%m") for l in linhas], "datasets": [
            {"label": "% Rendimento 1º passo", "data": [l["rend1"] for l in linhas]},
            {"label": "% Rendimento 2º passo", "data": [l["rend2"] for l in linhas]},
            {"label": "% Rendimento geral", "data": [l["rendimento"] for l in linhas]},
        ]}
    if aba == "ano":
        linhas = dados["linhas"]
        return {"tipo": "line", "meta": meta, "labels": [l["mes"] for l in linhas], "datasets": [
            {"label": "% Rendimento 1º passo", "data": [l["rend1"] for l in linhas]},
            {"label": "% Rendimento 2º passo", "data": [l["rend2"] for l in linhas]},
            {"label": "% Rendimento geral", "data": [l["rendimento"] for l in linhas]},
        ]}
    if aba in ("colaborador", "material"):
        linhas = dados["linhas"]
        return {"tipo": "line", "meta": meta, "labels": [l["data"].strftime("%d/%m") for l in linhas],
                "datasets": [{"label": "% Rendimento", "data": [l["rend"] for l in linhas]}]}
    if aba == "motivo":
        linhas = [l for l in dados["linhas"] if l["total"]]
        return {"tipo": "bar", "labels": [l["nome"] for l in linhas], "datasets": [{"label": "Retrabalho (peças)", "data": [l["total"] for l in linhas]}]}
    if aba == "diaria":
        linhas = [m for m in dados["motivos"] if m["qtd"]]
        return {"tipo": "bar", "labels": [m["nome"] for m in linhas], "datasets": [{"label": "Retrabalho (peças)", "data": [m["qtd"] for m in linhas]}]}
    return None


@login_required
def hc_dashboard(request):
    hc.garantir_padroes()
    aba = request.GET.get("aba", "consolidado")
    if aba not in {a[0] for a in ABAS_DASHBOARD}:
        aba = "consolidado"
    mes_ini, mes_fim, ultimo = _mes_referencia()
    ctx = {"abas": ABAS_DASHBOARD, "aba": aba, "meta": hc.meta(), "total_registros": RendimentoHCRegistro.objects.count()}

    if aba == "diaria":
        dia = _data(request.GET.get("data"), ultimo)
        ctx.update(dia=dia, dados=hc.analise_diaria(dia))
    elif aba == "ano":
        anos = hc.anos_disponiveis()
        ano = _inteiro(request.GET.get("ano"), anos[0])
        ctx.update(anos=anos, ano=ano, dados=hc.retrabalho_ano(ano))
    else:
        inicio, fim = _periodo(request, mes_ini, mes_fim)
        ctx.update(inicio=inicio, fim=fim)
        if aba == "motivo":
            ctx["dados"] = hc.retrabalho_motivo(inicio, fim)
        elif aba == "colaborador":
            chave = request.GET.get("colaborador", "")
            ctx.update(colaboradores=hc.lista_colaboradores(), colaborador_sel=chave,
                       dados=hc.analise_colaborador(chave, inicio, fim))
        elif aba == "material":
            materiais = list(HCCadastro.objects.filter(tipo=HCCadastro.TIPO_MATERIAL, ativo=True))
            mat_id = _inteiro(request.GET.get("material"), materiais[0].pk if materiais else None)
            ctx.update(materiais=materiais, material_sel=mat_id, dados=hc.rendimento_material(mat_id, inicio, fim))
        else:
            ctx["dados"] = hc.consolidado(inicio, fim)
    ctx["grafico"] = _grafico(aba, ctx.get("dados"))
    return render(request, "laboratorio/hc_dashboard.html", ctx)


# --------------------------------------------------------------------------- registros
@login_required
def hc_registros(request):
    qs = RendimentoHCRegistro.objects.select_related("colaborador", "turno", "tipo_garra")
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
        qs = qs.filter(Q(colaborador__nome_completo__icontains=busca) | Q(colaborador_nome__icontains=busca) | Q(numero_garra__icontains=busca))
    pagina = Paginator(qs, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "laboratorio/hc_registros.html", {
        "pagina": pagina, "turnos": RegraTurnoCoating.objects.filter(ativo=True),
        "inicio": request.GET.get("inicio", ""), "fim": request.GET.get("fim", ""), "turno_sel": turno, "q": busca,
        "querystring": params.urlencode(),
    })


@login_required
def hc_registro_create(request):
    form = hc.RegistroHCForm(request.POST or None, initial={"data": date.today()})
    if request.method == "POST" and form.is_valid():
        r = form.save(usuario=request.user)
        messages.success(request, f"Lançamento registrado: {r.qtd_lentes} lentes, {r.qtd_retrabalho} retrabalho(s).")
        if "salvar_novo" in request.POST:
            return redirect("laboratorio:hc_registro_create")
        return redirect("laboratorio:hc_registros")
    return render(request, "laboratorio/hc_registro_form.html", {"form": form, "titulo": "Novo lançamento de rendimento"})


@login_required
def hc_registro_update(request, pk):
    registro = get_object_or_404(RendimentoHCRegistro, pk=pk)
    form = hc.RegistroHCForm(request.POST or None, instance=registro)
    if request.method == "POST" and form.is_valid():
        form.save(usuario=request.user)
        messages.success(request, "Lançamento atualizado.")
        return redirect("laboratorio:hc_registros")
    return render(request, "laboratorio/hc_registro_form.html", {"form": form, "titulo": "Editar lançamento", "registro": registro})


@login_required
@require_POST
def hc_registro_delete(request, pk):
    get_object_or_404(RendimentoHCRegistro, pk=pk).delete()
    messages.success(request, "Lançamento excluído.")
    return redirect("laboratorio:hc_registros")


# --------------------------------------------------------------------------- configurações: campos do formulário
@login_required
def hc_config_campos(request):
    hc.garantir_padroes()
    return render(request, "laboratorio/hc_config_campos.html", {
        "campos": HCCampoFormulario.objects.all(), "tipos": HCCampoFormulario.TIPO_CHOICES,
        "config": RendimentoHCConfig.get(),
    })


@login_required
@require_POST
def hc_campo_save(request):
    pk = _inteiro(request.POST.get("id"))
    rotulo = (request.POST.get("rotulo") or "").strip()
    if not rotulo:
        messages.error(request, "Informe a pergunta/rótulo do campo.")
        return redirect("laboratorio:hc_config_campos")
    if pk:
        campo = get_object_or_404(HCCampoFormulario, pk=pk)
    else:
        base = slugify(rotulo)[:40] or "campo"
        chave, i = base, 2
        while HCCampoFormulario.objects.filter(chave=chave).exists():
            chave, i = f"{base}-{i}", i + 1
        ultimo = HCCampoFormulario.objects.order_by("-ordem").first()
        campo = HCCampoFormulario(chave=chave, ordem=(ultimo.ordem + 10) if ultimo else 0)
    campo.rotulo = rotulo[:200]
    campo.ajuda = (request.POST.get("ajuda") or "").strip()[:255]
    campo.obrigatorio = request.POST.get("obrigatorio") == "on"
    campo.visivel = request.POST.get("visivel") == "on" or campo.chave in HCCampoFormulario.CHAVES_OBRIGATORIAS
    if not campo.sistema:
        tipo = request.POST.get("tipo")
        campo.tipo = tipo if tipo in dict(HCCampoFormulario.TIPO_CHOICES) else HCCampoFormulario.TIPO_TEXTO
        campo.opcoes = (request.POST.get("opcoes") or "").strip()
        if campo.tipo == HCCampoFormulario.TIPO_SELECAO and not campo.lista_opcoes:
            messages.error(request, "Informe ao menos uma opção para o campo de lista suspensa.")
            return redirect("laboratorio:hc_config_campos")
    campo.save()
    messages.success(request, f"Campo '{campo.rotulo}' salvo.")
    return redirect("laboratorio:hc_config_campos")


@login_required
@require_POST
def hc_campo_mover(request, pk):
    campos = list(HCCampoFormulario.objects.all())
    idx = next((i for i, c in enumerate(campos) if c.pk == pk), None)
    if idx is None:
        return redirect("laboratorio:hc_config_campos")
    destino = idx - 1 if request.POST.get("direcao") == "up" else idx + 1
    if 0 <= destino < len(campos):
        campos[idx], campos[destino] = campos[destino], campos[idx]
        for i, c in enumerate(campos):
            if c.ordem != i * 10:
                HCCampoFormulario.objects.filter(pk=c.pk).update(ordem=i * 10)
    return redirect("laboratorio:hc_config_campos")


@login_required
@require_POST
def hc_campo_delete(request, pk):
    campo = get_object_or_404(HCCampoFormulario, pk=pk)
    if campo.sistema:
        messages.error(request, "Campos de sistema não podem ser excluídos; oculte-o se não for necessário.")
    else:
        campo.delete()
        messages.success(request, f"Campo '{campo.rotulo}' excluído (respostas já lançadas continuam guardadas).")
    return redirect("laboratorio:hc_config_campos")


@login_required
@require_POST
def hc_config_meta(request):
    try:
        valor = Decimal((request.POST.get("meta_rendimento") or "").replace(",", "."))
    except InvalidOperation:
        valor = None
    if valor is None or not (0 < valor <= 100):
        messages.error(request, "Meta inválida: informe um percentual entre 0 e 100.")
    else:
        config = RendimentoHCConfig.get()
        config.meta_rendimento = valor
        config.save()
        messages.success(request, f"Meta de rendimento atualizada para {valor}%.")
    return redirect("laboratorio:hc_config_campos")


# --------------------------------------------------------------------------- configurações: cadastros base
@login_required
def hc_config_cadastros(request):
    hc.garantir_padroes()
    aba = request.GET.get("aba", HCCadastro.TIPO_GARRA)
    tipos = dict(HCCadastro.TIPO_CHOICES)
    if aba != "EQUIPE" and aba not in tipos:
        aba = HCCadastro.TIPO_GARRA
    ctx = {"aba": aba, "tipos": HCCadastro.TIPO_CHOICES, "passos": HCCadastro.PASSO_CHOICES}
    if aba == "EQUIPE":
        ctx["equipe"] = EquipeHC.objects.select_related("colaborador")
        ids = ctx["equipe"].values_list("colaborador_id", flat=True)
        ctx["disponiveis"] = Colaborador.objects.filter(is_active=True).exclude(pk__in=ids).order_by("nome_completo")
    else:
        ctx["itens"] = HCCadastro.objects.filter(tipo=aba)
        ctx["tipo_nome"] = tipos[aba]
    return render(request, "laboratorio/hc_config_cadastros.html", ctx)


def _volta_cadastros(aba):
    return redirect(f"{reverse('laboratorio:hc_config_cadastros')}?aba={aba}")


@login_required
@require_POST
def hc_cadastro_save(request):
    tipo = request.POST.get("tipo")
    nome = (request.POST.get("nome") or "").strip()
    if tipo not in dict(HCCadastro.TIPO_CHOICES):
        return redirect("laboratorio:hc_config_cadastros")
    if not nome:
        messages.error(request, "Informe o nome.")
        return _volta_cadastros(tipo)
    pk = _inteiro(request.POST.get("id"))
    item = get_object_or_404(HCCadastro, pk=pk, tipo=tipo) if pk else HCCadastro(tipo=tipo)
    if HCCadastro.objects.filter(tipo=tipo, nome__iexact=nome).exclude(pk=item.pk).exists():
        messages.error(request, f"Já existe '{nome}' neste cadastro.")
        return _volta_cadastros(tipo)
    item.nome = nome[:120]
    ordem = _inteiro(request.POST.get("ordem"))
    if ordem is None:
        ultimo = HCCadastro.objects.filter(tipo=tipo).order_by("-ordem").first()
        ordem = (ultimo.ordem + 1) if ultimo else 0
    item.ordem = max(ordem, 0)
    item.ativo = (request.POST.get("ativo") == "on") if pk else True
    if tipo == HCCadastro.TIPO_GARRA:
        passo = _inteiro(request.POST.get("passo"))
        item.passo = passo if passo in (1, 2) else None
    item.save()
    messages.success(request, f"'{item.nome}' salvo.")
    return _volta_cadastros(tipo)


@login_required
@require_POST
def hc_cadastro_delete(request, pk):
    item = get_object_or_404(HCCadastro, pk=pk)
    if RendimentoHCItem.objects.filter(cadastro=item).exists() or RendimentoHCRegistro.objects.filter(tipo_garra=item).exists():
        item.ativo = False
        item.save(update_fields=["ativo"])
        messages.warning(request, f"'{item.nome}' já tem lançamentos; foi inativado em vez de excluído.")
    else:
        item.delete()
        messages.success(request, f"'{item.nome}' excluído.")
    return _volta_cadastros(item.tipo)


@login_required
@require_POST
def hc_equipe_save(request):
    """Adiciona colaborador à Equipe HC ou atualiza apelidos/ativo."""
    pk = _inteiro(request.POST.get("id"))
    if pk:
        membro = get_object_or_404(EquipeHC, pk=pk)
        membro.apelidos = (request.POST.get("apelidos") or "").strip()[:255]
        membro.ativo = request.POST.get("ativo") == "on"
        membro.save()
        messages.success(request, f"{membro.colaborador.nome_completo} atualizado.")
    else:
        colab = get_object_or_404(Colaborador, pk=_inteiro(request.POST.get("colaborador"), 0))
        EquipeHC.objects.get_or_create(colaborador=colab, defaults={"apelidos": (request.POST.get("apelidos") or "").strip()[:255]})
        messages.success(request, f"{colab.nome_completo} adicionado à Equipe HC.")
    return _volta_cadastros("EQUIPE")


@login_required
@require_POST
def hc_equipe_delete(request, pk):
    membro = get_object_or_404(EquipeHC, pk=pk)
    membro.delete()
    messages.success(request, f"{membro.colaborador.nome_completo} removido da Equipe HC.")
    return _volta_cadastros("EQUIPE")


# --------------------------------------------------------------------------- configurações: integrações
@login_required
def hc_config_integracoes(request):
    hc.garantir_padroes()
    propostas = hc.propostas_sincronizacao()
    return render(request, "laboratorio/hc_config_integracoes.html", {
        "propostas": propostas,
        "colaboradores": Colaborador.objects.filter(is_active=True).order_by("nome_completo"),
        "turnos": RegraTurnoCoating.objects.all(),
        "tratamentos": TratamentoAntiReflexo.objects.all(),
        "tratamento_ativo": next((c for c in HCCampoFormulario.objects.filter(chave="tratamento")), None),
        "tem_dados": RendimentoHCRegistro.objects.exists(),
    })


@login_required
@require_POST
def hc_sincronizar(request):
    novos, desativados = hc.aplicar_sincronizacao()
    messages.success(request, f"Sincronização concluída: {novos} colaborador(es) adicionado(s) e {desativados} desativado(s) na Equipe HC.")
    return redirect("laboratorio:hc_config_integracoes")


@login_required
@require_POST
def hc_vincular_nome(request):
    """Vincula um nome digitado nos lançamentos antigos a um colaborador do RH (e guarda como apelido)."""
    nome = request.POST.get("nome", "")
    colab = get_object_or_404(Colaborador, pk=_inteiro(request.POST.get("colaborador"), 0))
    n = RendimentoHCRegistro.objects.filter(colaborador__isnull=True, colaborador_nome=nome).update(colaborador=colab)
    membro, _ = EquipeHC.objects.get_or_create(colaborador=colab)
    apelidos = [a.strip() for a in membro.apelidos.split(",") if a.strip()]
    if nome and nome not in apelidos:
        membro.apelidos = ", ".join(apelidos + [nome])[:255]
        membro.save(update_fields=["apelidos"])
    messages.success(request, f"{n} lançamento(s) de '{nome}' vinculados a {colab.nome_completo}.")
    return redirect("laboratorio:hc_config_integracoes")


# --------------------------------------------------------------------------- importação de planilha
MAX_UPLOAD = 15 * 1024 * 1024


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
def hc_importar(request):
    """Tela de importação: o navegador consulta o preview (cabeçalhos) e envia arquivo + mapeamento aqui."""
    hc.garantir_padroes()
    resultado = None
    if request.method == "POST":
        try:
            dados = _ler_upload(request)
            mapa = {k[4:]: v for k, v in request.POST.items() if k.startswith("map_") and v != ""}
            resultado = imp.importar(
                dados["linhas"], mapa, a_partir=_data(request.POST.get("a_partir"), None),
                simular=request.POST.get("acao") == "simular", usuario=request.user,
            )
            if resultado["simulado"]:
                messages.info(request, f"Simulação: {resultado['validas']} lançamento(s) seriam importados. Nada foi gravado.")
            else:
                messages.success(request, f"{resultado['importadas']} lançamento(s) importados.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "laboratorio/hc_importar.html", {"alvos": imp.alvos(), "resultado": resultado})


@login_required
@require_POST
def hc_importar_preview(request):
    try:
        dados = _ler_upload(request)
    except ValueError as exc:
        return JsonResponse({"erro": str(exc)}, status=400)
    amostra = [["" if v is None else str(v)[:40] for v in linha] for linha in dados["linhas"][:2]]
    return JsonResponse({
        "abas": dados["abas"], "aba": dados["aba"], "cabecalhos": dados["cabecalhos"], "total": len(dados["linhas"]),
        "sugestao": imp.sugerir_mapa(dados["cabecalhos"]), "amostra": amostra,
    })
