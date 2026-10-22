import datetime
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from pcp.forms import (CampoForm, PaginaOrganizacaoForm, ImportarPlanilhaForm, FormularioForm, FrequenciaForm, ListaOpcoesForm, NovaRevisaoForm,
                       PaginaForm, TurnoForm)
from pcp import pendencias as pend
from pcp.importacao import importar_planilha
from pcp.models import (SEM_GRUPO, Campo, Formulario, FormularioVersao, Frequencia, GrupoPagina, ListaOpcoes, Ocorrencia,
                        Pagina, Resposta, Turno, Verificacao)


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
def formulario_excluir(request, pk):
    """Exclui o formulário com todas as revisões, páginas e campos (para importar de novo).

    Sem verificações lançadas basta confirmar. Com lançamentos, é preciso marcar a exclusão do histórico e digitar o código."""
    formulario = get_object_or_404(Formulario.objects.select_related('setor'), pk=pk)
    resumo = {
        'revisoes': formulario.versoes.count(),
        'paginas': Pagina.objects.filter(versao__formulario=formulario).count(),
        'campos': Campo.objects.filter(pagina__versao__formulario=formulario).count(),
        'verificacoes': Verificacao.objects.filter(pagina__versao__formulario=formulario).count(),
        'ocorrencias': Ocorrencia.objects.filter(verificacao__pagina__versao__formulario=formulario).count(),
    }
    erro = ''
    if request.method == 'POST':
        if resumo['verificacoes']:
            if not request.POST.get('apagar_historico'):
                erro = 'Marque a opção de excluir também o histórico de verificações.'
            elif (request.POST.get('codigo') or '').strip().upper() != formulario.codigo.upper():
                erro = f'Digite o código {formulario.codigo} para confirmar.'
        if not erro:
            codigo = formulario.codigo
            with transaction.atomic():
                Verificacao.objects.filter(pagina__versao__formulario=formulario).delete()  # respostas e ocorrências vão junto
                formulario.delete()
            messages.success(request, f'Formulário {codigo} excluído. Já é possível importá-lo novamente.')
            return redirect('pcp:formularios')
    return render(request, 'pcp/formulario_excluir.html', {'formulario': formulario, 'resumo': resumo, 'erro': erro})


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
    return render(request, 'pcp/versao_detalhe.html', {'versao': versao, 'grupos': versao.formulario.ordenar_grupos(grupos), 'total_paginas': len(paginas)})


@login_required
@require_POST
def versao_publicar(request, pk):
    versao = get_object_or_404(FormularioVersao, pk=pk)
    if _bloqueia_edicao(request, versao):
        return redirect('pcp:versao_detalhe', pk)
    if not versao.paginas.exists():
        messages.error(request, 'Cadastre ao menos uma página antes de publicar.')
        return redirect('pcp:versao_detalhe', pk)
    vigencia = request.POST.get('vigencia')
    if vigencia:
        versao.vigencia = _parse_data(vigencia)
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
    travada = not pagina.versao.editavel
    form_class = PaginaOrganizacaoForm if travada else PaginaForm
    form = form_class(request.POST or None, instance=pagina)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if 'grupo' in form.changed_data:
            pagina.versao.formulario.atribuir_grupo([pagina.nome], pagina.grupo)  # vale para as páginas de mesmo nome nas outras revisões
        messages.success(request, 'Página atualizada.')
        return redirect('pcp:pagina_detalhe', pk)
    return render(request, 'pcp/form_generico.html', {
        'form': form, 'titulo': f'Editar página {pagina.nome}', 'voltar': 'pcp:pagina_detalhe', 'voltar_pk': pk,
        'ajuda': 'Esta revisão está travada: só grupo, ordem e máquina podem ser ajustados. '
                 'Nome e campos mudam numa nova revisão.' if travada else ''})


def _nome_grupo(texto):
    return ' '.join((texto or '').split())[:80]


def _volta_grupos(formulario_id, filtro=''):
    url = reverse('pcp:grupos', args=[formulario_id])
    return redirect(f'{url}?{urlencode({"grupo": filtro})}' if filtro else url)


@login_required
def versao_grupos(request, pk):
    """Atalho antigo: os grupos agora são gerenciados por formulário."""
    versao = get_object_or_404(FormularioVersao, pk=pk)
    return redirect('pcp:grupos', versao.formulario_id)


@login_required
def grupos(request, pk):
    """Gerencia os grupos do formulário e associa páginas a eles (individualmente ou em massa)."""
    formulario = get_object_or_404(Formulario.objects.select_related('setor'), pk=pk)
    versao = formulario.versao_vigente or formulario.versoes.first()
    paginas = list(versao.paginas.annotate(n_campos=Count('campos'))) if versao else []
    for nome in sorted({p.grupo for p in paginas if p.grupo}):  # grupos que só existiam no texto da página
        formulario.garantir_grupo(nome)
    contagem = Counter(p.grupo for p in paginas)
    lista_grupos = [{'obj': g, 'n': contagem.get(g.nome, 0)} for g in formulario.grupos.all()]
    ordem = {g['obj'].nome: i for i, g in enumerate(lista_grupos)}
    filtro = request.GET.get('grupo', '')
    if filtro == '__sem__':
        visiveis = [p for p in paginas if not p.grupo]
    elif filtro:
        visiveis = [p for p in paginas if p.grupo == filtro]
    else:
        visiveis = list(paginas)
    visiveis.sort(key=lambda p: (ordem.get(p.grupo, 10 ** 6) if p.grupo else 10 ** 7, p.ordem, p.nome))
    return render(request, 'pcp/grupos.html', {
        'formulario': formulario, 'versao': versao, 'grupos': lista_grupos, 'paginas': visiveis, 'filtro': filtro,
        'total': len(paginas), 'sem_grupo': contagem.get('', 0), 'inativas': sum(1 for p in paginas if not p.ativo)})


@login_required
@require_POST
def grupo_criar(request, pk):
    formulario = get_object_or_404(Formulario, pk=pk)
    nome = _nome_grupo(request.POST.get('nome'))
    if not nome or nome.lower() == SEM_GRUPO.lower():
        messages.error(request, 'Informe um nome válido para o grupo.')
    elif formulario.grupos.filter(nome__iexact=nome).exists():
        messages.warning(request, f'O grupo "{nome}" já existe.')
    else:
        formulario.garantir_grupo(nome)
        messages.success(request, f'Grupo "{nome}" criado.')
    return _volta_grupos(pk, request.POST.get('filtro', ''))


@login_required
@require_POST
def grupo_renomear(request, pk):
    grupo = get_object_or_404(GrupoPagina.objects.select_related('formulario'), pk=pk)
    formulario = grupo.formulario
    novo = _nome_grupo(request.POST.get('nome'))
    if not novo or novo.lower() == SEM_GRUPO.lower():
        messages.error(request, 'Informe um nome válido para o grupo.')
        return _volta_grupos(formulario.pk)
    if novo != grupo.nome:
        existente = formulario.grupos.filter(nome__iexact=novo).exclude(pk=grupo.pk).first()
        with transaction.atomic():
            destino = existente.nome if existente else novo
            Pagina.objects.filter(versao__formulario=formulario, grupo=grupo.nome).update(grupo=destino)
            if existente:
                grupo.delete()  # fusão: as páginas já foram para o grupo existente
            else:
                grupo.nome = novo
                grupo.save(update_fields=['nome'])
        messages.success(request, f'Grupo renomeado para "{destino}"' + (' (unido ao grupo existente).' if existente else '.'))
    return _volta_grupos(formulario.pk, novo if request.POST.get('filtro') else '')


@login_required
@require_POST
def grupo_excluir(request, pk):
    grupo = get_object_or_404(GrupoPagina.objects.select_related('formulario'), pk=pk)
    formulario = grupo.formulario
    with transaction.atomic():
        n = Pagina.objects.filter(versao__formulario=formulario, grupo=grupo.nome, versao__status__in=['vigente', 'rascunho']).count()
        Pagina.objects.filter(versao__formulario=formulario, grupo=grupo.nome).update(grupo='')
        grupo.delete()
    messages.success(request, f'Grupo "{grupo.nome}" excluído.' + (f' {n} página(s) ficaram sem grupo.' if n else ''))
    return _volta_grupos(formulario.pk)


@login_required
@require_POST
def grupo_mover(request, pk):
    """Sobe ou desce o grupo na ordem de exibição."""
    grupo = get_object_or_404(GrupoPagina.objects.select_related('formulario'), pk=pk)
    itens = list(grupo.formulario.grupos.all())
    for i, g in enumerate(itens):  # normaliza a ordem (0..n) antes de trocar
        if g.ordem != i:
            g.ordem = i
            g.save(update_fields=['ordem'])
    i = next(k for k, g in enumerate(itens) if g.pk == grupo.pk)
    j = i - 1 if request.POST.get('dir') == 'up' else i + 1
    if 0 <= j < len(itens):
        itens[i].ordem, itens[j].ordem = itens[j].ordem, itens[i].ordem
        itens[i].save(update_fields=['ordem'])
        itens[j].save(update_fields=['ordem'])
    return _volta_grupos(grupo.formulario_id, request.POST.get('filtro', ''))


@login_required
@require_POST
def paginas_acao(request, pk):
    """Ação em massa sobre as páginas selecionadas: mover/remover de grupo, desativar, reativar ou excluir."""
    formulario = get_object_or_404(Formulario, pk=pk)
    filtro = request.POST.get('filtro', '')
    paginas = list(Pagina.objects.filter(pk__in=request.POST.getlist('paginas'), versao__formulario=formulario))
    acao = request.POST.get('acao')
    if not paginas:
        messages.warning(request, 'Selecione ao menos uma página.')
        return _volta_grupos(pk, filtro)
    nomes = sorted({p.nome for p in paginas})
    if acao in ('mover', 'remover'):
        destino = ''
        if acao == 'mover':
            destino = request.POST.get('destino', '')
            if destino == '__novo__':
                destino = _nome_grupo(request.POST.get('novo_nome'))
                if not destino or destino.lower() == SEM_GRUPO.lower():
                    messages.error(request, 'Informe o nome do novo grupo.')
                    return _volta_grupos(pk, filtro)
            elif not formulario.grupos.filter(nome=destino).exists():
                messages.error(request, 'Escolha o grupo de destino.')
                return _volta_grupos(pk, filtro)
        formulario.atribuir_grupo(nomes, destino)
        messages.success(request, f'{len(nomes)} página(s) ' + (f'movida(s) para "{destino}".' if destino else 'removida(s) do grupo.'))
    elif acao in ('desativar', 'ativar'):
        formulario.paginas_equivalentes(nomes).update(ativo=(acao == 'ativar'))
        messages.success(request, f'{len(nomes)} página(s) ' + ('reativada(s).' if acao == 'ativar' else 'desativada(s): saem do preenchimento, das pendências e dos atrasos; o histórico é mantido.'))
    elif acao == 'excluir':
        excluidas, bloqueadas = set(), set()
        for p in formulario.paginas_equivalentes(nomes):
            try:
                p.delete()
                excluidas.add(p.nome)
            except ProtectedError:
                bloqueadas.add(p.nome)
        if excluidas - bloqueadas:
            messages.success(request, f'{len(excluidas - bloqueadas)} página(s) excluída(s).')
        if bloqueadas:
            messages.warning(request, f'{len(bloqueadas)} página(s) não foram excluídas por já terem verificações lançadas ({", ".join(sorted(bloqueadas))}). '
                                      'Desative-as para tirá-las do preenchimento sem perder o histórico.')
    else:
        messages.error(request, 'Escolha uma ação.')
    return _volta_grupos(pk, filtro)


@login_required
@require_POST
def pagina_excluir(request, pk):
    """Exclui o bloco (página) em qualquer revisão, desde que sem verificações lançadas; senão, orienta a desativar."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao'), pk=pk)
    versao_id, nome = pagina.versao_id, pagina.nome
    try:
        pagina.delete()
    except ProtectedError:
        messages.error(request, f'A página "{nome}" já tem verificações lançadas e não pode ser excluída (o histórico seria perdido). '
                                'Desative-a para tirá-la do preenchimento, das pendências e dos atrasos.')
        return redirect('pcp:pagina_detalhe', pk)
    messages.success(request, f'Página "{nome}" excluída.')
    return redirect('pcp:versao_detalhe', versao_id)


@login_required
@require_POST
def pagina_alternar(request, pk):
    """Ativa/desativa o bloco. Desativado: não aparece no preenchimento nem entra em pendências e atrasos; o histórico fica."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    novo = not pagina.ativo
    pagina.versao.formulario.paginas_equivalentes([pagina.nome]).update(ativo=novo)
    pagina.ativo = novo
    messages.success(request, f'Página "{pagina.nome}" {"reativada" if novo else "desativada"}.')
    return redirect('pcp:pagina_detalhe', pk)


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
    """Exclui o item em qualquer revisão, desde que sem respostas lançadas; senão, orienta a desativar."""
    campo = get_object_or_404(Campo, pk=pk)
    pagina_id = campo.pagina_id
    try:
        campo.delete()
    except ProtectedError:
        messages.error(request, 'Este item já tem respostas lançadas e não pode ser excluído. Desative-o para deixar de exigir o preenchimento.')
        return redirect('pcp:pagina_detalhe', pagina_id)
    messages.success(request, 'Item excluído.')
    return redirect('pcp:pagina_detalhe', pagina_id)


@login_required
@require_POST
def campo_alternar(request, pk):
    """Ativa/desativa o item: desativado deixa de ser exigido (e de gerar pendência) sem perder as respostas."""
    campo = get_object_or_404(Campo.objects.select_related('pagina__versao__formulario'), pk=pk)
    novo = not campo.ativo
    paginas = campo.pagina.versao.formulario.paginas_equivalentes([campo.pagina.nome])
    Campo.objects.filter(pagina__in=paginas, item=campo.item, etapa=campo.etapa, descricao=campo.descricao).update(ativo=novo)
    messages.success(request, f'Item {"reativado" if novo else "desativado"}.')
    return redirect('pcp:pagina_detalhe', campo.pagina_id)


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
    return _cadastro_lista(request, 'Turnos', Turno.objects.all(), [('sigla', 'Sigla'), ('nome', 'Nome'), ('horario', 'Horário'), ('ordem', 'Ordem')], 'pcp:turno_novo', 'pcp:turno_editar', 'pcp:turno_excluir')


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
        blocos.append({'versao': v, 'grupos': v.formulario.ordenar_grupos(grupos)})
    return render(request, 'pcp/preencher.html', {'blocos': blocos, 'hoje': timezone.localdate()})


@login_required
def pendencias(request):
    """Painel de pendências: por data, quais verificações devidas ainda não foram feitas em cada página e turno."""
    data = _parse_data(request.GET.get('data'))
    turnos_ativos = list(Turno.objects.filter(ativo=True))
    formulario_id = request.GET.get('formulario') or None
    if formulario_id and not str(formulario_id).isdigit():
        formulario_id = None
    painel = pend.painel(data, turnos_ativos, formulario_id)
    return render(request, 'pcp/pendencias.html', {
        'data': data, 'turnos': turnos_ativos, 'painel': painel, 'formularios': Formulario.objects.filter(ativo=True),
        'formulario_id': int(formulario_id) if formulario_id else None, 'hoje': timezone.localdate()})


PERIODOS_ATRASO = [7, 14, 30, 60]


def _periodo_atrasos(request):
    hoje = timezone.localdate()
    ontem = hoje - datetime.timedelta(days=1)
    fim = min(_parse_data(request.GET.get('ate')) if request.GET.get('ate') else ontem, ontem)
    dias = int(request.GET['dias']) if request.GET.get('dias') in {str(d) for d in PERIODOS_ATRASO} else 7
    return fim - datetime.timedelta(days=dias - 1), fim, dias, hoje


@login_required
def atrasos(request):
    """Atrasos do período encerrado: verificações devidas cujo prazo passou sem resposta, por página e data."""
    ini, fim, dias, hoje = _periodo_atrasos(request)
    turnos_ativos = list(Turno.objects.filter(ativo=True))
    formulario_id = request.GET.get('formulario') if str(request.GET.get('formulario', '')).isdigit() else None
    painel = pend.painel_atrasos(ini, fim, turnos_ativos, formulario_id, hoje)
    return render(request, 'pcp/atrasos.html', {
        'ini': ini, 'fim': fim, 'dias': dias, 'periodos': PERIODOS_ATRASO, 'painel': painel, 'hoje': hoje,
        'formularios': Formulario.objects.filter(ativo=True),
        'formulario_id': int(formulario_id) if formulario_id else None})


@login_required
def atrasos_pagina(request, pk):
    """Detalhe dos itens em atraso de uma página no período."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    ini, fim, dias, hoje = _periodo_atrasos(request)
    turnos_ativos = list(Turno.objects.filter(ativo=True))
    lista, devidos = pend.atrasos_pagina(pagina, ini, fim, turnos_ativos, hoje, pend.inicio_rastreio(pagina.versao.formulario))
    lista.sort(key=lambda a: (a['fim'], a['turno'].ordem if a['turno'] else 0, a['campo'].ordem), reverse=True)
    return render(request, 'pcp/atrasos_pagina.html', {
        'pagina': pagina, 'versao': pagina.versao, 'atrasos': lista, 'devidos': devidos, 'ini': ini, 'fim': fim, 'dias': dias,
        'turno_padrao': turnos_ativos[0] if turnos_ativos else None})


@login_required
def preencher_pagina(request, pk):
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario', 'maquina'), pk=pk)
    data = _parse_data(request.GET.get('data'))
    turnos_ativos = list(Turno.objects.filter(ativo=True))
    turno = next((t for t in turnos_ativos if str(t.pk) == request.GET.get('turno')), turnos_ativos[0] if turnos_ativos else None)
    verificacao = Verificacao.objects.filter(pagina=pagina, data=data, turno=turno).first() if turno else None
    respostas = {r.campo_id: r for r in verificacao.respostas.all()} if verificacao else {}
    devidos = pend.avaliar_pagina(pagina, data, [turno])[turno.pk] if turno else {}
    linhas = []
    for campo in pagina.campos.filter(ativo=True).select_related('frequencia', 'lista').prefetch_related('lista__opcoes'):
        resposta = respostas.get(campo.pk)
        devido = campo.pk in devidos
        linhas.append({'campo': campo, 'resposta': resposta, 'devido': devido,
                       'pendente': devido and not devidos[campo.pk] and not (resposta and resposta.valor)})
    ocorrencias_dia = verificacao.ocorrencias.select_related('campo') if verificacao else []
    return render(request, 'pcp/preencher_pagina.html', {
        'pagina': pagina, 'versao': pagina.versao, 'data': data, 'turno': turno, 'turnos': turnos_ativos,
        'linhas': linhas, 'verificacao': verificacao, 'ocorrencias': ocorrencias_dia,
        'travada': pagina.versao.status != FormularioVersao.VIGENTE,
        'n_devidos': sum(1 for l in linhas if l['devido']), 'n_pendentes': sum(1 for l in linhas if l['pendente']),
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
