import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from pcp.forms import (CampoForm, ImportarPlanilhaForm, FormularioForm, FrequenciaForm, ListaOpcoesForm, NovaRevisaoForm,
                       PaginaForm, TurnoForm)
from pcp.importacao import importar_planilha
from pcp.models import (Campo, Formulario, FormularioVersao, Frequencia, ListaOpcoes, Ocorrencia, Pagina,
                        Resposta, Turno, Verificacao)


# --------------------------------------------------------------------------------------
# Formulários, revisões, páginas e campos
# --------------------------------------------------------------------------------------

def _bloqueia_edicao(request, versao):
    """Revisão vigente/obsoleta é travada: a mudança deve nascer como nova revisão."""
    if versao.editavel:
        return False
    messages.warning(request, f'A revisão {versao} está {versao.get_status_display().lower()} e não pode ser editada. '
                              'Crie uma nova revisão para alterar a estrutura.')
    return True


@login_required
def formularios(request):
    lista = Formulario.objects.select_related('setor').annotate(n_versoes=Count('versoes'))
    for f in lista:
        f.vigente = f.versao_vigente
    return render(request, 'pcp/formularios.html', {'formularios': lista})


@login_required
def formulario_novo(request):
    form = FormularioForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        formulario = form.save()
        messages.success(request, f'Formulário {formulario.codigo} criado. Cadastre agora a primeira revisão.')
        return redirect('pcp:versao_nova', formulario.pk)
    return render(request, 'pcp/form_generico.html', {'form': form, 'titulo': 'Novo formulário', 'voltar': 'pcp:formularios'})


@login_required
def formulario_editar(request, pk):
    formulario = get_object_or_404(Formulario, pk=pk)
    form = FormularioForm(request.POST or None, instance=formulario)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Formulário atualizado.')
        return redirect('pcp:formulario_detalhe', pk)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Editar {formulario.codigo}', 'voltar': 'pcp:formulario_detalhe', 'voltar_pk': pk})


@login_required
def formulario_detalhe(request, pk):
    formulario = get_object_or_404(Formulario.objects.select_related('setor'), pk=pk)
    versoes = formulario.versoes.annotate(n_paginas=Count('paginas', distinct=True))
    return render(request, 'pcp/formulario_detalhe.html', {'formulario': formulario, 'versoes': versoes})


@login_required
def versao_nova(request, pk):
    """Cria uma revisão. Havendo revisão anterior, parte de uma cópia da estrutura mais recente."""
    formulario = get_object_or_404(Formulario, pk=pk)
    base = formulario.versoes.first()
    inicial = {'revisao': base.proxima_revisao() if base else 'R00'}
    form = NovaRevisaoForm(request.POST or None, initial=inicial)
    if request.method == 'POST' and form.is_valid():
        rev = form.cleaned_data['revisao'].strip()
        if formulario.versoes.filter(revisao=rev).exists():
            form.add_error('revisao', 'Já existe uma revisão com este código.')
        else:
            with transaction.atomic():
                if base:
                    nova = base.clonar(rev, request.user, form.cleaned_data['motivo'])
                else:
                    nova = FormularioVersao.objects.create(
                        formulario=formulario, revisao=rev, motivo=form.cleaned_data['motivo'], criado_por=request.user)
            messages.success(request, f'Revisão {nova} criada como rascunho.')
            return redirect('pcp:versao_detalhe', nova.pk)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Nova revisão de {formulario.codigo}',
        'ajuda': 'A nova revisão nasce como rascunho, com uma cópia das páginas e campos da revisão mais recente. '
                 'Edite à vontade e publique quando estiver pronta; a revisão vigente continua valendo até lá.' if base else '',
        'voltar': 'pcp:formulario_detalhe', 'voltar_pk': pk})


@login_required
def versao_detalhe(request, pk):
    versao = get_object_or_404(FormularioVersao.objects.select_related('formulario__setor'), pk=pk)
    paginas = versao.paginas.annotate(n_campos=Count('campos')).select_related('maquina')
    grupos = {}
    for p in paginas:
        grupos.setdefault(p.grupo or 'Sem grupo', []).append(p)
    return render(request, 'pcp/versao_detalhe.html', {'versao': versao, 'grupos': grupos, 'total_paginas': len(paginas)})


@login_required
@require_POST
def versao_publicar(request, pk):
    versao = get_object_or_404(FormularioVersao, pk=pk)
    if _bloqueia_edicao(request, versao):
        return redirect('pcp:versao_detalhe', pk)
    if not versao.paginas.exists():
        messages.error(request, 'Cadastre ao menos uma página antes de publicar.')
        return redirect('pcp:versao_detalhe', pk)
    versao.publicar()
    messages.success(request, f'Revisão {versao} publicada e vigente. A anterior foi marcada como obsoleta.')
    return redirect('pcp:formulario_detalhe', versao.formulario_id)


@login_required
@require_POST
def versao_excluir(request, pk):
    versao = get_object_or_404(FormularioVersao, pk=pk)
    formulario_id = versao.formulario_id
    if _bloqueia_edicao(request, versao):
        return redirect('pcp:versao_detalhe', pk)
    try:
        versao.delete()
    except ProtectedError:
        messages.error(request, 'Esta revisão já tem verificações lançadas e não pode ser excluída.')
        return redirect('pcp:versao_detalhe', pk)
    messages.success(request, 'Rascunho excluído.')
    return redirect('pcp:formulario_detalhe', formulario_id)


@login_required
def pagina_nova(request, pk):
    versao = get_object_or_404(FormularioVersao, pk=pk)
    if _bloqueia_edicao(request, versao):
        return redirect('pcp:versao_detalhe', pk)
    form = PaginaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        pagina = form.save(commit=False)
        pagina.versao = versao
        pagina.save()
        messages.success(request, f'Página "{pagina.nome}" criada.')
        return redirect('pcp:pagina_detalhe', pagina.pk)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Nova página em {versao}', 'voltar': 'pcp:versao_detalhe', 'voltar_pk': pk})


@login_required
def pagina_detalhe(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario', 'maquina'), pk=pk)
    campos = pagina.campos.select_related('frequencia', 'lista')
    return render(request, 'pcp/pagina_detalhe.html', {'pagina': pagina, 'versao': pagina.versao, 'campos': campos})


@login_required
def pagina_editar(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao'), pk=pk)
    if _bloqueia_edicao(request, pagina.versao):
        return redirect('pcp:pagina_detalhe', pk)
    form = PaginaForm(request.POST or None, instance=pagina)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Página atualizada.')
        return redirect('pcp:pagina_detalhe', pk)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Editar página {pagina.nome}', 'voltar': 'pcp:pagina_detalhe', 'voltar_pk': pk})


@login_required
@require_POST
def pagina_excluir(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao'), pk=pk)
    versao_id = pagina.versao_id
    if _bloqueia_edicao(request, pagina.versao):
        return redirect('pcp:pagina_detalhe', pk)
    try:
        pagina.delete()
    except ProtectedError:
        messages.error(request, 'Esta página já tem verificações lançadas e não pode ser excluída.')
        return redirect('pcp:pagina_detalhe', pk)
    messages.success(request, 'Página excluída.')
    return redirect('pcp:versao_detalhe', versao_id)


@login_required
def campo_novo(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao'), pk=pk)
    if _bloqueia_edicao(request, pagina.versao):
        return redirect('pcp:pagina_detalhe', pk)
    proxima = (pagina.campos.order_by('-ordem').values_list('ordem', flat=True).first() or 0) + 1
    form = CampoForm(request.POST or None, initial={'ordem': proxima})
    if request.method == 'POST' and form.is_valid():
        campo = form.save(commit=False)
        campo.pagina = pagina
        campo.save()
        messages.success(request, 'Campo criado.')
        return redirect('pcp:pagina_detalhe', pk)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Novo campo em {pagina.nome}', 'voltar': 'pcp:pagina_detalhe', 'voltar_pk': pk})


@login_required
def campo_editar(request, pk):
    campo = get_object_or_404(Campo.objects.select_related('pagina__versao'), pk=pk)
    if _bloqueia_edicao(request, campo.pagina.versao):
        return redirect('pcp:pagina_detalhe', campo.pagina_id)
    form = CampoForm(request.POST or None, instance=campo)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Campo atualizado.')
        return redirect('pcp:pagina_detalhe', campo.pagina_id)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Editar campo {campo.item}', 'voltar': 'pcp:pagina_detalhe', 'voltar_pk': campo.pagina_id})


@login_required
@require_POST
def campo_excluir(request, pk):
    campo = get_object_or_404(Campo.objects.select_related('pagina__versao'), pk=pk)
    pagina_id = campo.pagina_id
    if _bloqueia_edicao(request, campo.pagina.versao):
        return redirect('pcp:pagina_detalhe', pagina_id)
    try:
        campo.delete()
    except ProtectedError:
        messages.error(request, 'Este campo já tem respostas lançadas e não pode ser excluído.')
        return redirect('pcp:pagina_detalhe', pagina_id)
    messages.success(request, 'Campo excluído.')
    return redirect('pcp:pagina_detalhe', pagina_id)


@login_required
def importar(request):
    """Importa a estrutura de um formulário a partir da planilha como nova revisão (rascunho por padrão)."""
    form = ImportarPlanilhaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            r = importar_planilha(
                d['arquivo'], nome_arquivo=d['arquivo'].name, setor=d['setor'], codigo=d['codigo'], revisao=d['revisao'],
                titulo=d['titulo'], usuario=request.user, publicar=d['publicar'], substituir=d['substituir'])
        except ValueError as e:
            form.add_error(None, str(e))
        except Exception:  # planilha corrompida ou fora do padrão
            form.add_error('arquivo', 'Não foi possível ler a planilha. Confira se é um .xlsx válido no padrão dos formulários de PCP.')
        else:
            messages.success(request, f'Revisão {r["versao"]} importada como {r["versao"].get_status_display().lower()}: '
                                      f'{len(r["paginas"])} páginas e {r["total_campos"]} campos.')
            if r['ignoradas']:
                messages.warning(request, 'Abas não importadas: ' + '; '.join(f'{a} ({m})' for a, m in r['ignoradas']))
            return redirect('pcp:versao_detalhe', r['versao'].pk)
    return render(request, 'pcp/importar.html', {'form': form})


# --------------------------------------------------------------------------------------
# Cadastros base: turnos, frequências e listas de opções
# --------------------------------------------------------------------------------------

def _cadastro_lista(request, titulo, itens, colunas, novo, editar, excluir):
    linhas = []
    for obj in itens:
        valores = []
        for attr, _ in colunas:
            v = getattr(obj, attr)
            valores.append(v() if callable(v) else v)
        linhas.append({'obj': obj, 'valores': valores})
    return render(request, 'pcp/cadastro_lista.html', {
        'titulo': titulo, 'linhas': linhas, 'cabecalhos': [c for _, c in colunas],
        'secao_atual': {'Turnos': 'turnos', 'Frequências': 'frequencias', 'Listas de opções': 'listas'}.get(titulo, ''),
        'novo': novo, 'editar': editar, 'excluir': excluir})


def _cadastro_form(request, pk, model, form_class, lista_url, titulo):
    obj = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{titulo} salvo.')
        return redirect(lista_url)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'{"Editar" if obj else "Novo(a)"} {titulo.lower()}', 'voltar': lista_url})


def _cadastro_excluir(request, pk, model, lista_url, titulo):
    obj = get_object_or_404(model, pk=pk)
    try:
        obj.delete()
        messages.success(request, f'{titulo} excluído.')
    except ProtectedError:
        messages.error(request, f'{titulo} está em uso e não pode ser excluído. Desative-o para deixar de usá-lo.')
    return redirect(lista_url)


@login_required
def turnos(request):
    return _cadastro_lista(request, 'Turnos', Turno.objects.all(), [('sigla', 'Sigla'), ('nome', 'Nome'), ('ordem', 'Ordem')], 'pcp:turno_novo', 'pcp:turno_editar', 'pcp:turno_excluir')


@login_required
def turno_form(request, pk=None):
    return _cadastro_form(request, pk, Turno, TurnoForm, 'pcp:turnos', 'Turno')


@login_required
@require_POST
def turno_excluir(request, pk):
    return _cadastro_excluir(request, pk, Turno, 'pcp:turnos', 'Turno')


@login_required
def frequencias(request):
    return _cadastro_lista(
        request, 'Frequências', Frequencia.objects.all(),
        [('nome', 'Nome'), ('get_periodicidade_display', 'Periodicidade'), ('ordem', 'Ordem')],
        'pcp:frequencia_nova', 'pcp:frequencia_editar', 'pcp:frequencia_excluir')


@login_required
def frequencia_form(request, pk=None):
    return _cadastro_form(request, pk, Frequencia, FrequenciaForm, 'pcp:frequencias', 'Frequência')


@login_required
@require_POST
def frequencia_excluir(request, pk):
    return _cadastro_excluir(request, pk, Frequencia, 'pcp:frequencias', 'Frequência')


@login_required
def listas(request):
    return _cadastro_lista(
        request, 'Listas de opções', ListaOpcoes.objects.prefetch_related('opcoes'),
        [('nome', 'Nome'), ('opcoes_resumo', 'Opções')],
        'pcp:lista_nova', 'pcp:lista_editar', 'pcp:lista_excluir')


@login_required
def lista_form(request, pk=None):
    obj = get_object_or_404(ListaOpcoes, pk=pk) if pk else None
    form = ListaOpcoesForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, 'Lista salva.')
        return redirect('pcp:listas')
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': 'Editar lista de opções' if obj else 'Nova lista de opções', 'voltar': 'pcp:listas'})


@login_required
@require_POST
def lista_excluir(request, pk):
    return _cadastro_excluir(request, pk, ListaOpcoes, 'pcp:listas', 'Lista')


# --------------------------------------------------------------------------------------
# Preenchimento das verificações e ocorrências
# --------------------------------------------------------------------------------------

def _parse_data(valor):
    try:
        return datetime.date.fromisoformat(valor)
    except (TypeError, ValueError):
        return timezone.localdate()


@login_required
def preencher(request):
    """Escolha da página a preencher: revisões vigentes agrupadas por formulário e grupo."""
    vigentes = (FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
                .select_related('formulario__setor').prefetch_related('paginas'))
    blocos = []
    for v in vigentes:
        grupos = {}
        for p in v.paginas.all():
            if p.ativo:
                grupos.setdefault(p.grupo or 'Sem grupo', []).append(p)
        blocos.append({'versao': v, 'grupos': grupos})
    return render(request, 'pcp/preencher.html', {'blocos': blocos, 'hoje': timezone.localdate()})


@login_required
def preencher_pagina(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario', 'maquina'), pk=pk)
    data = _parse_data(request.GET.get('data'))
    turnos_ativos = list(Turno.objects.filter(ativo=True))
    turno = next((t for t in turnos_ativos if str(t.pk) == request.GET.get('turno')), turnos_ativos[0] if turnos_ativos else None)
    verificacao = Verificacao.objects.filter(pagina=pagina, data=data, turno=turno).first() if turno else None
    respostas = {r.campo_id: r for r in verificacao.respostas.all()} if verificacao else {}
    linhas = []
    for campo in pagina.campos.filter(ativo=True).select_related('frequencia', 'lista').prefetch_related('lista__opcoes'):
        linhas.append({'campo': campo, 'resposta': respostas.get(campo.pk)})
    ocorrencias_dia = verificacao.ocorrencias.select_related('campo') if verificacao else []
    return render(request, 'pcp/preencher_pagina.html', {
        'pagina': pagina, 'versao': pagina.versao, 'data': data, 'turno': turno, 'turnos': turnos_ativos,
        'linhas': linhas, 'verificacao': verificacao, 'ocorrencias': ocorrencias_dia,
        'travada': pagina.versao.status != FormularioVersao.VIGENTE,
        'tipos_ocorrencia': Ocorrencia.TIPOS,
    })


@login_required
@require_POST
def preencher_salvar(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao'), pk=pk)
    data = _parse_data(request.POST.get('data'))
    turno = get_object_or_404(Turno, pk=request.POST.get('turno'))
    retorno = f'{reverse("pcp:preencher_pagina", args=[pk])}?data={data.isoformat()}&turno={turno.pk}'
    if pagina.versao.status != FormularioVersao.VIGENTE:
        messages.error(request, 'Só é possível lançar verificações na revisão vigente.')
        return redirect(retorno)

    fora = []
    with transaction.atomic():
        verificacao, _ = Verificacao.objects.get_or_create(
            pagina=pagina, data=data, turno=turno, defaults={'responsavel': request.user})
        for campo in pagina.campos.filter(ativo=True).select_related('lista').prefetch_related('lista__opcoes'):
            valor = (request.POST.get(f'c_{campo.pk}') or '').strip()
            if not valor:
                Resposta.objects.filter(verificacao=verificacao, campo=campo).delete()
                continue
            conforme = campo.avaliar(valor)
            Resposta.objects.update_or_create(
                verificacao=verificacao, campo=campo, defaults={'valor': valor, 'conforme': conforme})
            if conforme is False:
                fora.append(campo.item or campo.descricao)

        descricao = (request.POST.get('oc_descricao') or '').strip()
        if descricao:
            tipo = request.POST.get('oc_tipo')
            campo_oc = pagina.campos.filter(pk=request.POST.get('oc_campo') or None).first()
            Ocorrencia.objects.create(
                verificacao=verificacao, campo=campo_oc, descricao=descricao, criado_por=request.user,
                tipo=tipo if tipo in dict(Ocorrencia.TIPOS) else Ocorrencia.OBSERVACAO)

    messages.success(request, 'Verificação salva.')
    if fora:
        messages.warning(request, 'Fora da especificação: ' + ', '.join(fora) +
                         '. Registre uma ocorrência que requer tratativa, se necessário.')
    return redirect(retorno)


@login_required
def ocorrencias(request):
    status = request.GET.get('status', 'abertas')
    qs = Ocorrencia.objects.select_related('verificacao__pagina__versao__formulario', 'verificacao__turno', 'campo', 'criado_por')
    if status == 'abertas':
        qs = qs.filter(tipo=Ocorrencia.TRATATIVA, status=Ocorrencia.ABERTA)
    elif status == 'tratadas':
        qs = qs.filter(tipo=Ocorrencia.TRATATIVA, status=Ocorrencia.TRATADA)
    elif status == 'observacoes':
        qs = qs.filter(tipo=Ocorrencia.OBSERVACAO)
    termo = (request.GET.get('q') or '').strip()
    if termo:
        qs = qs.filter(Q(descricao__icontains=termo) | Q(verificacao__pagina__nome__icontains=termo)
                       | Q(campo__descricao__icontains=termo))
    return render(request, 'pcp/ocorrencias.html', {'ocorrencias': qs[:300], 'status': status, 'q': termo})


@login_required
@require_POST
def ocorrencia_tratar(request, pk):
    oc = get_object_or_404(Ocorrencia, pk=pk, tipo=Ocorrencia.TRATATIVA)
    texto = (request.POST.get('tratativa') or '').strip()
    if not texto:
        messages.error(request, 'Descreva a tratativa realizada.')
    else:
        oc.tratativa, oc.status = texto, Ocorrencia.TRATADA
        oc.tratada_por, oc.tratada_em = request.user, timezone.now()
        oc.save()
        messages.success(request, 'Tratativa registrada.')
    return redirect('pcp:ocorrencias')
