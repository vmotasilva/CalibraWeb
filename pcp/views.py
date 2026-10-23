import datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_POST

from pcp.forms import (TemplatePaginaForm, CampoForm, PaginaOrganizacaoForm, ImportarPlanilhaForm, ImportarRegistrosForm, FormularioForm, FrequenciaForm, ListaOpcoesForm, NovaRevisaoForm,
                       PaginaForm, TurnoForm)
from pcp import exportacao
from pcp import templates_xlsx
from pcp import pendencias as pend
from pcp import semana as semana_mod
from pcp import equivalencias as equiv
from pcp import tipos as tipos_mod
from pcp.tipos import aplicar_ajuste
from pcp.importacao import importar_planilha
from pcp.importacao_registros import importar_registros
from pcp.models import (TemplatePagina, SEM_GRUPO, AjusteCampo, AjusteVinculo, Campo, Formulario, FormularioVersao, Frequencia, GrupoPagina, ListaOpcoes, Ocorrencia,
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


def _decimal_ou_none(texto):
    texto = (texto or '').strip().replace(',', '.')
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValueError(texto)


def _descricao_estado(estado, listas):
    """Texto curto do estado de um item: 'Lista: Ok / Nok', 'Número 10 – 27 °C', 'Texto'."""
    tipo = dict(Campo.TIPOS).get(estado['tipo'], estado['tipo'])
    if estado['tipo'] == Campo.LISTA:
        return f'Lista: {listas.get(estado["lista"], "—")}'
    if estado['tipo'] == Campo.NUMERO:
        faixa = f'{estado["minimo"] or "—"} – {estado["maximo"] or "—"}' if (estado['minimo'] or estado['maximo']) else 'sem limites'
        return f'{tipo}: {faixa} {estado["unidade"]}'.strip()
    return tipo


@login_required
def ajustes(request, pk):
    """Histórico dos ajustes de tipo, texto livre, limites e vínculos de valores, com a opção de desfazer."""
    formulario = get_object_or_404(Formulario, pk=pk)
    if request.method == 'POST':
        escolhidos = []
        for valor in request.POST.getlist('ajustes'):
            tipo, _, numero = valor.partition(':') if ':' in valor else ('c', '', valor)  # número puro = ajuste de item
            if numero.isdigit():
                escolhidos.append((tipo, int(numero)))
        itens = [a for a in AjusteCampo.objects.filter(formulario=formulario, pk__in=[n for t, n in escolhidos if t == 'c']).select_related('campo')]
        itens += [a for a in AjusteVinculo.objects.filter(formulario=formulario, pk__in=[n for t, n in escolhidos if t == 'v']).select_related('opcao', 'lista')]
        itens.sort(key=lambda a: (a.criado_em, a.pk), reverse=True)  # o mais recente primeiro
        resultados = Counter()
        for a in itens:
            resultados[(equiv.desfazer_vinculo if isinstance(a, AjusteVinculo) else tipos_mod.desfazer)(a, request.user)] += 1
        if resultados['ok']:
            messages.success(request, f'{resultados["ok"]} ajuste(s) desfeito(s): itens e lançamentos voltaram ao estado anterior e a conformidade foi recalculada.')
        if resultados['parcial']:
            messages.warning(request, f'{resultados["parcial"]} vínculo(s) desfeito(s) parcialmente: alguns lançamentos foram editados depois e foram mantidos como estão.')
        if resultados['alterado']:
            messages.warning(request, f'{resultados["alterado"]} ajuste(s) não foram desfeitos porque o item ou os lançamentos mudaram depois '
                                      '(desfaça primeiro o ajuste mais recente ou edite manualmente).')
        if resultados['ja']:
            messages.info(request, f'{resultados["ja"]} ajuste(s) já estavam desfeitos.')
        if not resultados:
            messages.info(request, 'Nenhum ajuste selecionado.')
        return redirect('pcp:ajustes', pk)

    origem = request.GET.get('origem', '')
    listas = {l.pk: l.nome for l in ListaOpcoes.objects.all()}
    linhas = []
    if origem in ('', 'tipo', 'texto', 'limites'):
        qs = AjusteCampo.objects.filter(formulario=formulario).select_related('campo__pagina', 'criado_por', 'desfeito_por')
        if origem:
            qs = qs.filter(origem=origem)
        for a in qs[:300]:
            linhas.append({
                'chave': f'c:{a.pk}', 'obj': a, 'quando': a.criado_em, 'tipo': a.origem, 'rotulo': a.get_origem_display(),
                'item': f'{a.campo.pagina.nome} · {a.campo.item or a.campo.descricao[:40]}',
                'antes': _descricao_estado(a.antes, listas), 'depois': _descricao_estado(a.depois, listas)})
    if origem in ('', 'vinculo'):
        for a in AjusteVinculo.objects.filter(formulario=formulario).select_related('opcao', 'lista', 'criado_por', 'desfeito_por')[:300]:
            destino = a.opcao.valor if a.opcao else '(opção removida)'
            linhas.append({
                'chave': f'v:{a.pk}', 'obj': a, 'quando': a.criado_em, 'tipo': 'vinculo', 'rotulo': a.get_acao_display(),
                'item': f'Lista "{a.lista.nome}" · {a.total} lançamento(s)',
                'antes': f'«{a.valor}»', 'depois': destino if a.acao == AjusteVinculo.VINCULO else f'«{a.valor}» como opção ({"conforme" if a.opcao and a.opcao.conforme else "desvio"})'})
    linhas.sort(key=lambda l: l['quando'], reverse=True)
    linhas = linhas[:300]
    return render(request, 'pcp/ajustes.html', {
        'formulario': formulario, 'linhas': linhas, 'origem': origem,
        'origens': list(AjusteCampo.ORIGENS) + [('vinculo', 'Valores vinculados a opções')],
        'pendentes': sum(1 for l in linhas if not l['obj'].desfeito)})


@login_required
def valores(request, pk):
    """Valores já lançados que não correspondem às opções cadastradas, com sugestão de vínculo."""
    formulario = get_object_or_404(Formulario, pk=pk)
    linhas, numericos = equiv.valores_do_formulario(formulario)
    return render(request, 'pcp/valores.html', {'formulario': formulario, 'linhas': linhas, 'numericos': numericos})


@login_required
@require_POST
def vincular_valores(request):
    """Aplica os vínculos escolhidos (tela de valores ou relatório da importação de registros)."""
    try:
        total = min(int(request.POST.get('total', 0)), 500)
    except ValueError:
        total = 0
    escolhas = []
    for i in range(total):
        acao = request.POST.get(f'acao_{i}', '')
        lista_id = request.POST.get(f'lista_{i}', '')
        if acao and lista_id.isdigit():
            escolhas.append((int(lista_id), request.POST.get(f'valor_{i}', ''), acao, request.POST.get(f'itens_{i}', '')))
    formulario = Formulario.objects.filter(pk=request.POST['formulario']).first() if request.POST.get('formulario', '').isdigit() else None
    r = equiv.aplicar_vinculos(escolhas, usuario=request.user, lote=tipos_mod.novo_lote(), formulario=formulario)
    if escolhas:
        partes = [f'{r["vinculados"]} valor(es) vinculado(s)', f'{r["criadas"]} opção(ões) criada(s)', f'{r["textos"]} item(ns) marcado(s) como texto']
        messages.success(request, ', '.join(partes) + f'; {r["lancamentos"]} lançamento(s) atualizado(s). Os vínculos valem nas próximas importações de registros.')
    else:
        messages.info(request, 'Nenhuma alteração: todas as linhas ficaram em "Manter como está".')
    if request.POST.get('next') == 'importar_registros':
        return redirect('pcp:importar_registros')
    formulario_id = request.POST.get('formulario', '')
    return redirect('pcp:valores', int(formulario_id)) if formulario_id.isdigit() else redirect('pcp:formularios')


@login_required
def sugerir_limites(request, pk):
    """Sugere mínimo e máximo dos itens numéricos (da especificação ou do histórico); aplica o que for marcado, com valores editáveis."""
    formulario = get_object_or_404(Formulario, pk=pk)
    versao = formulario.versao_vigente or formulario.versoes.first()
    if request.method == 'POST' and versao:
        aplicados, fora, invalidos, lote = 0, 0, 0, tipos_mod.novo_lote()
        for campo_id in request.POST.getlist('campos'):
            campo = Campo.objects.filter(pk=campo_id, pagina__versao__formulario=formulario, tipo=Campo.NUMERO).select_related('pagina').first()
            if not campo:
                continue
            try:
                minimo, maximo = _decimal_ou_none(request.POST.get(f'min_{campo_id}')), _decimal_ou_none(request.POST.get(f'max_{campo_id}'))
            except ValueError:
                invalidos += 1
                continue
            if (minimo is None and maximo is None) or (minimo is not None and maximo is not None and minimo > maximo):
                invalidos += 1
                continue
            fora += tipos_mod.aplicar_limites(formulario, campo, minimo, maximo, request.POST.get(f'un_{campo_id}', ''),
                                              usuario=request.user, lote=lote)
            aplicados += 1
        if aplicados:
            messages.success(request, f'Limites aplicados em {aplicados} item(ns); a conformidade dos lançamentos foi recalculada ({fora} fora do limite).')
        if invalidos:
            messages.warning(request, f'{invalidos} item(ns) não foram alterados por limites inválidos (vazios ou mínimo maior que o máximo).')
        if not aplicados and not invalidos:
            messages.info(request, 'Nenhum item selecionado.')
        return redirect('pcp:sugerir_limites', pk)
    cobertura = int(request.GET['cobertura']) if request.GET.get('cobertura') in {str(c) for c in tipos_mod.COBERTURAS} else 99
    propostas = tipos_mod.propor_limites(versao, cobertura) if versao else []
    return render(request, 'pcp/sugerir_limites.html', {
        'formulario': formulario, 'versao': versao, 'propostas': propostas, 'cobertura': cobertura,
        'coberturas': tipos_mod.COBERTURAS, 'minimo': tipos_mod.MIN_LANCAMENTOS_LIMITES})


@login_required
def ajustar_tipos(request, pk):
    """Prévia e aplicação do ajuste do tipo dos itens pelos lançamentos já feitos."""
    formulario = get_object_or_404(Formulario, pk=pk)
    versao = formulario.versao_vigente or formulario.versoes.first()
    if request.method == 'POST' and versao:
        aplicados, lote = 0, tipos_mod.novo_lote()
        for item in request.POST.getlist('campos'):
            campo_id, _, novo_tipo = item.partition('|')
            if novo_tipo not in (Campo.NUMERO, Campo.TEXTO) or not campo_id.isdigit():
                continue
            campo = Campo.objects.filter(pk=campo_id, pagina__versao__formulario=formulario, tipo=Campo.LISTA).select_related('pagina').first()
            if campo:
                aplicar_ajuste(formulario, campo, novo_tipo, usuario=request.user, lote=lote)
                aplicados += 1
        messages.success(request, f'Tipo ajustado em {aplicados} item(ns).' if aplicados else 'Nenhum item selecionado.')
        return redirect('pcp:ajustar_tipos', pk)
    propostas = tipos_mod.propor_ajustes(versao) if versao else []
    return render(request, 'pcp/ajustar_tipos.html', {'formulario': formulario, 'versao': versao, 'propostas': propostas,
                                                      'minimo': tipos_mod.MIN_LANCAMENTOS})


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
    paginas = versao.paginas.annotate(n_campos=Count('campos')).select_related('maquina').order_by('grupo', 'ordem', 'nome')
    grupos = {}
    for p in paginas:
        grupos.setdefault(p.grupo or 'Sem grupo', []).append(p)
    return render(request, 'pcp/versao_detalhe.html', {'versao': versao, 'grupos': versao.formulario.ordenar_grupos(grupos), 'total_paginas': len(paginas)})


@login_required
@require_POST
def versao_vigencia(request, pk):
    """Ajusta a data de vigência da revisão (início do rastreio de pendências e atrasos). Vale em qualquer status."""
    versao = get_object_or_404(FormularioVersao.objects.select_related('formulario'), pk=pk)
    texto = (request.POST.get('vigencia') or '').strip()
    if not texto:
        messages.error(request, 'Informe a data de vigência.')
        return redirect('pcp:versao_detalhe', pk)
    try:
        nova = datetime.date.fromisoformat(texto)
    except ValueError:
        messages.error(request, 'Data de vigência inválida.')
        return redirect('pcp:versao_detalhe', pk)
    versao.vigencia = nova
    versao.save(update_fields=['vigencia'])
    invalidar_dashboard()
    inicio = pend.inicio_rastreio(versao.formulario)
    messages.success(request, f'Vigência de {versao} ajustada para {nova:%d/%m/%Y}. O rastreio de pendências e atrasos do formulário começa em '
                              f'{inicio:%d/%m/%Y} (a menor vigência entre as revisões).')
    return redirect('pcp:versao_detalhe', pk)


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
        versao.formulario.posicionar_pagina(pagina, pagina.ordem)
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
        if 'ordem' in form.changed_data:
            pagina.versao.formulario.posicionar_pagina(pagina, pagina.ordem)
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


def _chave_natural(texto):
    """'DLP (10)' depois de 'DLP (2)': números comparados como números."""
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', (texto or '').lower())]


def _paginas_do_grupo(versao, grupo):
    return sorted(versao.paginas.filter(grupo=grupo), key=lambda p: (p.ordem, _chave_natural(p.nome)))


@login_required
@require_POST
def pagina_mover(request, pk):
    """Sobe ou desce a página dentro do grupo dela (a ordem vale para as páginas de mesmo nome nas outras revisões)."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    irmas = _paginas_do_grupo(pagina.versao, pagina.grupo)
    i = next(k for k, p in enumerate(irmas) if p.pk == pagina.pk)
    j = i - 1 if request.POST.get('dir') == 'up' else i + 1
    if 0 <= j < len(irmas):
        irmas[i], irmas[j] = irmas[j], irmas[i]
    pagina.versao.formulario.definir_ordem_paginas(pagina.versao, [p.nome for p in irmas])
    return _volta_grupos(pagina.versao.formulario_id, request.POST.get('filtro', ''))


@login_required
@require_POST
def grupo_ordenar(request, pk):
    """Ordena as páginas de um grupo (ou as sem grupo) em ordem alfabética natural."""
    formulario = get_object_or_404(Formulario, pk=pk)
    versao = formulario.versao_vigente or formulario.versoes.first()
    filtro = request.POST.get('filtro', '')
    if versao:
        grupo = '' if filtro == '__sem__' else filtro
        paginas = sorted(versao.paginas.filter(grupo=grupo), key=lambda p: _chave_natural(p.nome))
        formulario.definir_ordem_paginas(versao, [p.nome for p in paginas])
        messages.success(request, f'{len(paginas)} página(s) ordenada(s) de A a Z.')
    return _volta_grupos(pk, filtro)


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
    visiveis.sort(key=lambda p: (ordem.get(p.grupo, 10 ** 6) if p.grupo else 10 ** 7, p.ordem, _chave_natural(p.nome)))
    for i, p in enumerate(visiveis):
        p.pode_subir = i > 0 and visiveis[i - 1].grupo == p.grupo
        p.pode_descer = i < len(visiveis) - 1 and visiveis[i + 1].grupo == p.grupo
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
    invalidar_dashboard()  # mover de grupo, desativar ou excluir muda o que o dashboard mostra
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
    versao = FormularioVersao.objects.get(pk=versao_id)
    versao.formulario.renumerar_paginas(versao)
    messages.success(request, f'Página "{nome}" excluída.')
    return redirect('pcp:versao_detalhe', versao_id)


@login_required
@require_POST
def pagina_desativar(request, pk):
    """Desativa o bloco (página) sem apagar o histórico e volta para a tela de origem (ex.: ranking do dashboard).
    Desativada, a página sai do preenchimento, das pendências, dos atrasos, do sino e do dashboard; pode ser reativada em Grupos e blocos."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    formulario = pagina.versao.formulario
    formulario.paginas_equivalentes([pagina.nome]).update(ativo=False)
    invalidar_dashboard()
    messages.success(request, f'Página "{pagina.nome}" desativada. Para reativá-la: Formulários > {formulario.codigo} > Grupos e blocos.')
    destino = request.POST.get('next', '')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(destino)
    return redirect('pcp:pagina_detalhe', pk)


@login_required
@require_POST
def pagina_alternar(request, pk):
    """Ativa/desativa o bloco. Desativado: não aparece no preenchimento nem entra em pendências e atrasos; o histórico fica."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    novo = not pagina.ativo
    pagina.versao.formulario.paginas_equivalentes([pagina.nome]).update(ativo=novo)
    pagina.ativo = novo
    invalidar_dashboard()
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
        pagina.mover_campo(campo, campo.ordem)
        messages.success(request, f'Campo criado (Nº {Campo.objects.get(pk=campo.pk).ordem}).')
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
        if 'ordem' in form.changed_data:
            chaves = campo.pagina.mover_campo(campo, campo.ordem)
            campo.pagina.versao.formulario.aplicar_ordem_campos(campo.pagina.nome, chaves)
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
    Pagina.objects.get(pk=pagina_id).renumerar_campos()
    messages.success(request, 'Item excluído. Os Nºs do bloco foram renumerados.')
    return redirect('pcp:pagina_detalhe', pagina_id)


@login_required
@require_POST
def campo_mover(request, pk):
    """Sobe, desce ou posiciona o item no Nº informado dentro do bloco; vale em qualquer revisão e nas páginas de mesmo nome."""
    campo = get_object_or_404(Campo.objects.select_related('pagina__versao__formulario'), pk=pk)
    pagina = campo.pagina
    direcao = request.POST.get('dir')
    if direcao in ('up', 'down'):
        posicao = campo.ordem + (-1 if direcao == 'up' else 1)
    else:
        try:
            posicao = int(request.POST.get('posicao', ''))
        except ValueError:
            messages.error(request, 'Informe o Nº (um número inteiro a partir de 1).')
            return redirect('pcp:pagina_detalhe', pagina.pk)
    chaves = pagina.mover_campo(campo, posicao)
    pagina.versao.formulario.aplicar_ordem_campos(pagina.nome, chaves)
    return redirect('pcp:pagina_detalhe', pagina.pk)


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


@login_required
def importar_registros_view(request):
    """Importa os registros (lançamentos) das planilhas: separado da importação da estrutura."""
    form = ImportarRegistrosForm(request.POST or None, request.FILES or None)
    resumo = None
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        try:
            resumo = importar_registros(
                d['arquivo'], nome_arquivo=d['arquivo'].name, ano=d['ano'], formulario=d['formulario'], revisao=d['revisao'],
                simular=d['simular'], rastreio_desde_primeiro=d['rastreio'], ajustar_tipos=d['ajustar_tipos'])
        except ValueError as e:
            form.add_error(None, str(e))
        except Exception:  # planilha corrompida ou fora do padrão
            form.add_error('arquivo', 'Não foi possível ler a planilha. Confira se é um .xlsx válido no padrão dos formulários de PCP.')
        else:
            if not resumo['simulado']:
                messages.success(request, f'{resumo["respostas_novas"]} respostas importadas em {resumo["versao"]}.')
                form = ImportarRegistrosForm()
    return render(request, 'pcp/importar_registros.html', {'form': form, 'resumo': resumo})


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


PERIODOS_DASHBOARD = [7, 14, 30, 60, 90]


def _geracao_dashboard():
    """Marca da 'geração' do cache do dashboard: trocá-la invalida os resultados guardados (ex.: ao desativar uma página)."""
    marca = cache.get('pcp:dashboard:geracao')
    if marca is None:
        marca = tipos_mod.novo_lote()
        cache.set('pcp:dashboard:geracao', marca, timeout=None)
    return marca


def invalidar_dashboard():
    cache.set('pcp:dashboard:geracao', tipos_mod.novo_lote(), timeout=None)


def _paginas_para_escolher():
    """[{'formulario', 'grupos': [(grupo, [páginas])]}] das páginas ativas das revisões vigentes, na ordem configurada."""
    blocos = []
    for versao in (FormularioVersao.objects.filter(status=FormularioVersao.VIGENTE, formulario__ativo=True)
                   .select_related('formulario').order_by('formulario__codigo')):
        grupos = {}
        for p in versao.paginas.filter(ativo=True):
            grupos.setdefault(p.grupo or 'Sem grupo', []).append(p)
        if grupos:
            blocos.append({'formulario': versao.formulario, 'grupos': list(versao.formulario.ordenar_grupos(grupos).items())})
    return blocos


@login_required
def semana(request):
    """Visão semanal de uma página: um farol (verde/vermelho...) por prazo de cada item, com pop-up dos dados que o compõem."""
    hoje = timezone.localdate()
    blocos = _paginas_para_escolher()
    todas = [p for b in blocos for _, ps in b['grupos'] for p in ps]
    escolhida = next((p for p in todas if str(p.pk) == request.GET.get('pagina')), todas[0] if todas else None)
    ref = _parse_data(request.GET.get('semana')) if request.GET.get('semana') else hoje
    contexto = {'blocos': blocos, 'pagina': escolhida, 'hoje': hoje}
    if escolhida:
        escolhida = Pagina.objects.select_related('versao__formulario', 'maquina').get(pk=escolhida.pk)
        dados = semana_mod.visao_semanal(escolhida, ref, hoje=hoje)
        for linha in dados['linhas']:
            linha['info'] = dados['itens'][linha['campo']]
            pontos = [d for dia in linha['dias'] for d in dia] + linha['janelas']
            linha['tem_nok'] = any(d['estado'] == 'nok' for d in pontos)
            novos = linha.get('novos') or [[] for _ in dados['dias']]
            linha['colunas'] = [{'hoje': dia['hoje'], 'pontos': pts, 'novos': nv} for dia, pts, nv in zip(dados['dias'], linha['dias'], novos)]
            linha['contagem'] = Counter(d['estado'] for d in pontos)
        ordem = {p: i for i, p in enumerate(pend.ORDEM_PERIODICIDADE)}
        frequencias = {}
        for i in dados['itens'].values():
            frequencias[i['frequencia_id']] = (ordem.get(i['periodicidade'], 98 if i['frequencia_id'] else 99), i['frequencia'])
        ordenadas = sorted(frequencias.items(), key=lambda kv: kv[1])
        # grupos por frequência (separador com sub-total), na ordem das frequências
        grupos = []
        for fid, (_, nome) in ordenadas:
            linhas_g = [l for l in dados['linhas'] if l['info']['frequencia_id'] == fid]
            total = Counter()
            for l in linhas_g:
                total.update(l['contagem'])
            grupos.append({'id': fid, 'nome': nome, 'linhas': linhas_g, 'ok': total['ok'], 'nok': total['nok'], 'aberto': total['aberto'],
                           'dispensado': total['dispensado'], 'registros': total['info'], 'sob_demanda': linhas_g[0]['tipo'] == 'eventos'})
        contexto.update({
            'd': dados, 'grupos': grupos, 'frequencias': [(k, v[1]) for k, v in ordenadas],
            'json_detalhes': {'itens': dados['itens'], 'detalhes': dados['detalhes']},
            'anterior': dados['ini'] - datetime.timedelta(days=7), 'proxima': dados['ini'] + datetime.timedelta(days=7),
            'esta_semana': semana_mod.segunda_feira(hoje), 'e_esta_semana': dados['ini'] == semana_mod.segunda_feira(hoje)})
    return render(request, 'pcp/semana.html', contexto)


@login_required
def dashboard(request):
    """Acompanhamento do cumprimento por página e frequência no período encerrado (até ontem)."""
    hoje = timezone.localdate()
    ontem = hoje - datetime.timedelta(days=1)
    fim = min(_parse_data(request.GET.get('ate')) if request.GET.get('ate') else ontem, ontem)
    dias = int(request.GET['dias']) if request.GET.get('dias') in {str(d) for d in PERIODOS_DASHBOARD} else 30
    ini = fim - datetime.timedelta(days=dias - 1)
    formulario_id = request.GET.get('formulario') if str(request.GET.get('formulario', '')).isdigit() else None
    chave_cache = f'pcp:dashboard:v3:{_geracao_dashboard()}:{ini}:{fim}:{formulario_id or 0}'
    dados = None if request.GET.get('atualizar') else cache.get(chave_cache)
    if dados is None:
        dados = pend.dashboard(ini, fim, list(Turno.objects.filter(ativo=True)), formulario_id, hoje)
        cache.set(chave_cache, dados, timeout=120)  # resultado simples (sem objetos de modelo); recarrega a cada 2 minutos
    grafico = {'evolucao': dados['evolucao'], 'frequencias': dados['por_frequencia'], 'agrupamento': dados['agrupamento']}
    # farol: situação dos prazos em andamento na data de observação (padrão: hoje); guardado por 1 minuto
    observar = _parse_data(request.GET.get('observar')) if request.GET.get('observar') else hoje
    chave_farol = f'pcp:farol:v2:{_geracao_dashboard()}:{observar}:{formulario_id or 0}'
    farol = None if request.GET.get('atualizar') else cache.get(chave_farol)
    if farol is None:
        farol = pend.farol(observar, formulario_id)
        cache.set(chave_farol, farol, timeout=60)
    ordem = request.GET.get('ordem') if request.GET.get('ordem') in ('pct', 'atrasos') else 'pct'
    top = int(request.GET['top']) if request.GET.get('top') in {str(t) for t in pend.TOPS} else 10
    rank_paginas, rank_itens = pend.ranking(dados, ordem, top)
    return render(request, 'pcp/dashboard.html', {
        'farol': farol, 'observar': observar, 'url_atual': request.get_full_path(), 'd': dados, 'grafico': grafico, 'rank_paginas': rank_paginas, 'rank_itens': rank_itens, 'ordem': ordem, 'top': top, 'tops': pend.TOPS,
        'min_pagina': pend.MIN_PRAZOS_PAGINA, 'min_item': pend.MIN_PRAZOS_ITEM, 'dias': dias, 'periodos': PERIODOS_DASHBOARD, 'hoje': hoje, 'fim': fim,
        'formularios': Formulario.objects.filter(ativo=True), 'formulario_id': int(formulario_id) if formulario_id else None})


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


def _periodo_mes(request):
    """(ano, mês) do parâmetro mes=AAAA-MM; padrão: o mês atual."""
    try:
        ano, mes = (int(x) for x in (request.GET.get('mes') or '').split('-'))
        if not (1 <= mes <= 12 and 2000 <= ano <= 2100):
            raise ValueError
    except ValueError:
        hoje = timezone.localdate()
        ano, mes = hoje.year, hoje.month
    return ano, mes


def _xlsx(wb, nome):
    nome = ''.join(c for c in unicodedata.normalize('NFKD', nome) if not unicodedata.combining(c))
    nome = re.sub(r'[^A-Za-z0-9._-]+', '_', nome).strip('_') or 'pcp'
    resposta = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resposta['Content-Disposition'] = f'attachment; filename="{nome}.xlsx"'
    wb.save(resposta)
    return resposta


@login_required
def exportar_pagina(request, pk):
    """Planilha do mês de uma página; turnos em manutenção/parada saem com todos os itens preenchidos com a situação."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    ano, mes = _periodo_mes(request)
    wb = exportacao.montar_planilha(pagina.versao.formulario, pagina.versao, [pagina], ano, mes)
    return _xlsx(wb, f'{pagina.versao.formulario.codigo}_{pagina.nome}_{ano}-{mes:02d}')


@login_required
def exportar_formulario(request, pk):
    """Planilha do mês com uma aba por página ativa do formulário (revisão vigente, ou a mais recente)."""
    formulario = get_object_or_404(Formulario, pk=pk)
    versao = formulario.versao_vigente or formulario.versoes.first()
    if versao is None:
        messages.warning(request, 'O formulário ainda não tem revisão para exportar.')
        return redirect('pcp:formulario_detalhe', pk)
    ano, mes = _periodo_mes(request)
    wb = exportacao.montar_planilha(formulario, versao, versao.paginas.filter(ativo=True), ano, mes)
    return _xlsx(wb, f'{formulario.codigo}_{versao.revisao}_{ano}-{mes:02d}')


def _periodo_dados(request):
    """(de, até) dos parâmetros de/ate (padrão: hoje); ordena e limita a 93 dias."""
    de = _parse_data(request.GET.get('de'))
    ate = _parse_data(request.GET.get('ate')) if request.GET.get('ate') else de
    if ate < de:
        de, ate = ate, de
    return de, min(ate, de + datetime.timedelta(days=92))


def _responder_dados(request, formulario, versao, paginas, nome, voltar):
    de, ate = _periodo_dados(request)
    paginas = list(paginas)
    n_turnos = Turno.objects.filter(ativo=True).count()
    estimativa = exportacao.estimar_linhas_dados(paginas, de, ate, n_turnos)
    somente = request.GET.get('somente_valor') == '1'
    if estimativa > exportacao.LIMITE_LINHAS_DADOS and not somente:
        messages.warning(request, f'O período gera cerca de {estimativa:,} linhas (limite de {exportacao.LIMITE_LINHAS_DADOS:,}). '
                                  'Reduza o período, escolha uma página ou marque "só com valor".'.replace(',', '.'))
        return redirect(*voltar)
    wb = exportacao.montar_dados(formulario, versao, paginas, de, ate, somente_com_valor=somente)
    return _xlsx(wb, f'{nome}_DADOS_{de:%Y%m%d}' + (f'_{ate:%Y%m%d}' if ate != de else ''))


@login_required
def exportar_dados_pagina(request, pk):
    """Exportação DADOS (tabela longa) de uma página no período."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario'), pk=pk)
    f = pagina.versao.formulario
    return _responder_dados(request, f, pagina.versao, [pagina], f'{f.codigo}_{pagina.nome}', ('pcp:preencher_pagina', pk))


@login_required
def exportar_dados_formulario(request, pk):
    """Exportação DADOS (tabela longa) de todas as páginas ativas do formulário (revisão vigente ou a mais recente) no período."""
    formulario = get_object_or_404(Formulario, pk=pk)
    versao = formulario.versao_vigente or formulario.versoes.first()
    if versao is None:
        messages.warning(request, 'O formulário ainda não tem revisão para exportar.')
        return redirect('pcp:formulario_detalhe', pk)
    return _responder_dados(request, formulario, versao, versao.paginas.filter(ativo=True).order_by('grupo', 'ordem', 'pk'),
                            f'{formulario.codigo}_{versao.revisao}', ('pcp:formulario_detalhe', pk))


def _catalogo_tags():
    """Variáveis aceitas, já com as chaves, para a tela de templates."""
    from pcp.templates_xlsx import ESCALARES, ITENS, LISTA
    grupos = [
        ('Cabeçalho (qualquer célula ou caixa de texto)', [('{{%s}}' % k, v) for k, v in ESCALARES.items()] + [
            ('{{DIA:1}} … {{DIA:31}}', 'Data do dia n do mês (dd/mm); vazio se o mês não tem o dia'),
            ('{{DIASEMANA:1}} … {{DIASEMANA:31}}', 'Dia da semana do dia n (seg, ter…)')]),
        ('Linha âncora (repetida para cada item)', [('{{%s}}' % k, v) for k, v in ITENS.items()]),
        ('Modo grade (itens nas linhas, dia/turno nas colunas)', [
            ('{{VALOR:1:T1}}', 'Valor do dia 1, turno T1 (ou posição: {{VALOR:1:1}}); turno em manutenção/parada traz a situação'),
            ('{{STATUS:1:T1}}', 'Situação da máquina no dia 1, turno T1')]),
        ('Modo lista (uma linha por item, data e turno preenchidos)', [('{{%s}}' % k, v) for k, v in LISTA.items()]),
    ]
    return grupos


@login_required
def templates_pagina(request):
    """Cadastro de templates de página: envio do .xlsx com variáveis, análise das tags e lista dos templates."""
    form = TemplatePaginaForm(request.POST or None, request.FILES or None, initial={'formulario': request.GET.get('formulario')})
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        conteudo = d['arquivo'].read()
        try:
            analise = templates_xlsx.analisar(conteudo)
        except ValueError as e:
            form.add_error('arquivo', str(e))
        else:
            tpl = TemplatePagina.objects.create(
                formulario=d['formulario'], nome=d['nome'], descricao=d['descricao'], pagina_nome=d['pagina_nome'].strip(),
                nome_arquivo_original=d['arquivo'].name[:255], arquivo_base64=templates_xlsx.codificar(conteudo), analise=analise,
                criado_por=request.user)
            messages.success(request, f'Template "{tpl.nome}" cadastrado: {len(analise["tags"])} variável(is) reconhecida(s), modo {analise["modo"] or "só cabeçalho"}.')
            if analise['desconhecidas']:
                messages.warning(request, 'Variáveis não reconhecidas (ficarão como estão na planilha): ' + ', '.join('{{%s}}' % t for t in analise['desconhecidas']))
            for aviso in analise['avisos']:
                messages.warning(request, aviso)
            return redirect('pcp:templates_pagina')
    templates = TemplatePagina.objects.select_related('formulario').defer('arquivo_base64')
    nomes_paginas = sorted(set(Pagina.objects.filter(ativo=True).values_list('nome', flat=True)))
    return render(request, 'pcp/templates_pagina.html', {'form': form, 'templates': templates, 'catalogo': _catalogo_tags(), 'nomes_paginas': nomes_paginas})


@login_required
def template_pagina_baixar(request, pk):
    """Baixa o arquivo original do template."""
    tpl = get_object_or_404(TemplatePagina, pk=pk)
    resposta = HttpResponse(templates_xlsx.decodificar(tpl.arquivo_base64), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    nome = re.sub(r'[^A-Za-z0-9._-]+', '_', tpl.nome_arquivo_original or f'{tpl.nome}.xlsx')
    resposta['Content-Disposition'] = f'attachment; filename="{nome}"'
    return resposta


@login_required
def template_pagina_amostra(request):
    """Baixa um template de exemplo com todas as variáveis (modo grade, modo lista e a documentação)."""
    resposta = HttpResponse(templates_xlsx.gerar_amostra().getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resposta['Content-Disposition'] = 'attachment; filename="modelo_template_pagina_PCP.xlsx"'
    return resposta


@login_required
@require_POST
def template_pagina_excluir(request, pk):
    tpl = get_object_or_404(TemplatePagina, pk=pk)
    nome = tpl.nome
    tpl.delete()
    messages.success(request, f'Template "{nome}" excluído.')
    return redirect('pcp:templates_pagina')


@login_required
@require_POST
def template_pagina_alternar(request, pk):
    tpl = get_object_or_404(TemplatePagina, pk=pk)
    tpl.ativo = not tpl.ativo
    tpl.save(update_fields=['ativo'])
    messages.success(request, f'Template "{tpl.nome}" {"ativado" if tpl.ativo else "desativado"}.')
    return redirect('pcp:templates_pagina')


@login_required
def exportar_template(request, pk):
    """Gera o PCP do mês de uma página no template escolhido (?template=ID&mes=AAAA-MM)."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao__formulario', 'maquina'), pk=pk)
    formulario = pagina.versao.formulario
    tpl = TemplatePagina.objects.filter(pk=request.GET.get('template') if str(request.GET.get('template', '')).isdigit() else None,
                                        formulario=formulario).first()
    if tpl is None or not tpl.serve_para(pagina):
        messages.error(request, 'Escolha um template ativo deste formulário (e que sirva para esta página).')
        return redirect('pcp:preencher_pagina', pk)
    ano, mes = _periodo_mes(request)
    try:
        saida = templates_xlsx.gerar(templates_xlsx.decodificar(tpl.arquivo_base64), formulario, pagina.versao, pagina, ano, mes)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('pcp:preencher_pagina', pk)
    nome = unicodedata.normalize('NFKD', f'{formulario.codigo}_{pagina.nome}_{ano}-{mes:02d}_{tpl.nome}')
    nome = re.sub(r'[^A-Za-z0-9._-]+', '_', ''.join(c for c in nome if not unicodedata.combining(c))).strip('_')
    resposta = HttpResponse(saida.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resposta['Content-Disposition'] = f'attachment; filename="{nome}.xlsx"'
    return resposta


@login_required
@require_POST
def preencher_status(request, pk):
    """Marca a máquina (página) como em manutenção, parada ou em operação num turno, no dia todo ou num período.
    Em manutenção/parada os itens deixam de ser obrigatórios (sem pendência nem atraso)."""
    pagina = get_object_or_404(Pagina.objects.select_related('versao'), pk=pk)
    data = _parse_data(request.POST.get('data'))
    turno = get_object_or_404(Turno, pk=request.POST.get('turno'))
    retorno = f'{reverse("pcp:preencher_pagina", args=[pk])}?data={data.isoformat()}&turno={turno.pk}'
    if pagina.versao.status != FormularioVersao.VIGENTE:
        messages.error(request, 'Só é possível alterar a situação da máquina na revisão vigente.')
        return redirect(retorno)
    status = request.POST.get('status', '')
    if status not in dict(Verificacao.STATUS_MAQUINA):
        messages.error(request, 'Escolha a situação da máquina.')
        return redirect(retorno)
    ate = _parse_data(request.POST.get('ate')) if request.POST.get('ate') else data
    if ate < data:
        ate = data
    ate = min(ate, data + datetime.timedelta(days=92))
    turnos = list(Turno.objects.filter(ativo=True)) if request.POST.get('escopo') == 'dia' else [turno]
    motivo = (request.POST.get('motivo') or '').strip()[:200]
    dias = [data + datetime.timedelta(days=n) for n in range((ate - data).days + 1)]
    marcados = 0
    with transaction.atomic():
        for dia in dias:
            for t in turnos:
                if status:
                    v, _ = Verificacao.objects.get_or_create(pagina=pagina, data=dia, turno=t, defaults={'responsavel': request.user})
                    Verificacao.objects.filter(pk=v.pk).update(status=status, motivo=motivo)
                    marcados += 1
                else:  # volta a operar: limpa a situação e remove verificações que só existiam por causa dela
                    for v in Verificacao.objects.filter(pagina=pagina, data=dia, turno=t).exclude(status=''):
                        v.status, v.motivo = '', ''
                        v.save(update_fields=['status', 'motivo'])
                        if not v.respostas.exists() and not v.ocorrencias.exists():
                            v.delete()
                        marcados += 1
    rotulo = dict(Verificacao.STATUS_MAQUINA)[status] if status else 'em operação'
    periodo = f'{data:%d/%m/%Y}' + (f' a {ate:%d/%m/%Y}' if ate != data else '')
    messages.success(request, f'Máquina "{pagina.nome}" marcada como {rotulo} em {marcados} turno(s) ({periodo}).'
                              + (' Os itens desses turnos não são mais obrigatórios.' if status else ''))
    return redirect(retorno)


def _frequencias_da_pagina(linhas):
    """[(frequencia_id ou 0, nome, quantidade)] das frequências dos itens da tela, na ordem de periodicidade; 0 = sem frequência."""
    contagem, nomes = {}, {}
    for l in linhas:
        f = l['campo'].frequencia
        chave_ = f.pk if f else 0
        contagem[chave_] = contagem.get(chave_, 0) + 1
        nomes[chave_] = (pend.ORDEM_PERIODICIDADE.index(f.periodicidade) if f and f.periodicidade in pend.ORDEM_PERIODICIDADE else 98 if f else 99,
                         f.ordem if f else 0, f.nome if f else 'Sem frequência')
    return [(k, nomes[k][2], contagem[k]) for k in sorted(contagem, key=lambda k: nomes[k])]


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
        opcoes_campo = [o.valor for o in campo.lista.opcoes.all()] if campo.tipo == 'lista' and campo.lista_id else []
        extra = resposta.valor if (resposta and resposta.valor and campo.tipo == 'lista' and resposta.valor not in opcoes_campo) else ''
        linhas.append({'campo': campo, 'resposta': resposta, 'valor_extra': extra, 'devido': devido,
                       'pendente': devido and not devidos[campo.pk] and not (resposta and resposta.valor)})
    ocorrencias_dia = verificacao.ocorrencias.select_related('campo') if verificacao else []
    return render(request, 'pcp/preencher_pagina.html', {
        'pagina': pagina, 'versao': pagina.versao, 'data': data, 'turno': turno, 'turnos': turnos_ativos,
        'linhas': linhas, 'verificacao': verificacao, 'ocorrencias': ocorrencias_dia,
        'travada': pagina.versao.status != FormularioVersao.VIGENTE,
        'n_devidos': sum(1 for l in linhas if l['devido']), 'n_pendentes': sum(1 for l in linhas if l['pendente']),
        'frequencias_pagina': _frequencias_da_pagina(linhas),
        'status': verificacao.status if verificacao else '', 'status_motivo': verificacao.motivo if verificacao else '',
        'status_rotulo': dict(Verificacao.STATUS_MAQUINA).get(verificacao.status, '') if verificacao else '',
        'status_opcoes': Verificacao.STATUS_MAQUINA, 'mes_atual': timezone.localdate().strftime('%Y-%m'),
        'templates_pagina': [t for t in TemplatePagina.objects.filter(formulario=pagina.versao.formulario, ativo=True).defer('arquivo_base64') if t.serve_para(pagina)],
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
