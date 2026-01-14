from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Max
from django.http import HttpResponse
import pandas as pd
from io import BytesIO
from datetime import datetime

from procedures.models import (
    PerfilTreinamento, 
    GrupoTreinamento, 
    SubGrupoTreinamento,
    ColaboradorPerfil,
    RegistroTreinamento,
    Procedimento
)
from procedures.forms.forms import (
    PerfilTreinamentoForm,
    GrupoTreinamentoForm,
    SubGrupoTreinamentoForm,
    ColaboradorPerfilForm
)


# ==================== FUNÇÕES AUXILIARES ====================

def criar_demandas_treinamento(colaborador_perfil, procedimentos):
    """
    Cria registros pendentes na matriz de treinamentos para os procedimentos necessários.
    Verifica se já existe registro antes de criar.
    """
    criados = 0
    ja_existem = 0
    
    for procedimento in procedimentos:
        # Verificar se já existe registro de treinamento
        existe = RegistroTreinamento.objects.filter(
            colaborador=colaborador_perfil.colaborador,
            procedimento=procedimento
        ).exists()
        
        if not existe:
            # Criar registro pendente (SEM data de treinamento - será preenchida quando treinar)
            RegistroTreinamento.objects.create(
                colaborador=colaborador_perfil.colaborador,
                procedimento=procedimento,
                revisao_treinada="0",  # Revisão 0 indica que ainda não foi treinado
                data_treinamento=None,  # Sem data - será preenchida no registro de treinamento
                validade_treinamento=None,
                observacoes=f"Demanda gerada automaticamente pelo perfil {colaborador_perfil.perfil.codigo}"
            )
            criados += 1
        else:
            ja_existem += 1
    
    return {'criados': criados, 'ja_existem': ja_existem}


@login_required
@require_http_methods(["POST"])
def associar_perfil_colaborador_view(request, colaborador_id):
    """
    Associa um colaborador a um novo perfil de treinamento,
    com seleção de grupos e subgrupos específicos.
    Cria demandas de treinamento automaticamente.
    """
    from rh.models import Colaborador
    from datetime import date
    import json
    
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    
    perfil_id = request.POST.get('perfil_id')
    grupos_selecionados = request.POST.getlist('grupos[]')
    subgrupos_selecionados = request.POST.getlist('subgrupos[]')
    
    if not perfil_id:
        messages.error(request, "Por favor, selecione um perfil.")
        return redirect('detalhe_colaborador', colab_id=colaborador_id)
    
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    # Verificar se já existe associação
    if ColaboradorPerfil.objects.filter(colaborador=colaborador, perfil=perfil, ativo=True).exists():
        messages.warning(request, f"O colaborador já está associado ao perfil {perfil.codigo}.")
        return redirect('detalhe_colaborador', colab_id=colaborador_id)
    
    # Converter IDs para inteiros
    grupos_ids = [int(g) for g in grupos_selecionados if g]
    subgrupos_ids = [int(s) for s in subgrupos_selecionados if s]
    
    # Criar associação
    colaborador_perfil = ColaboradorPerfil.objects.create(
        colaborador=colaborador,
        perfil=perfil,
        grupos_selecionados={
            'grupos': grupos_ids,
            'subgrupos': subgrupos_ids
        },
        data_atribuicao=date.today(),
        ativo=True,
        observacoes=f"Associado via página do colaborador em {date.today().strftime('%d/%m/%Y')}"
    )
    
    # Coletar procedimentos dos subgrupos selecionados
    procedimentos = []
    if subgrupos_ids:
        subgrupos = SubGrupoTreinamento.objects.filter(id__in=subgrupos_ids).prefetch_related('procedimentos')
        for subgrupo in subgrupos:
            procedimentos.extend(subgrupo.procedimentos.all())
    else:
        # Se não selecionou subgrupos específicos, pegar todos os procedimentos dos grupos
        if grupos_ids:
            grupos = GrupoTreinamento.objects.filter(id__in=grupos_ids).prefetch_related('subgrupos__procedimentos')
            for grupo in grupos:
                for subgrupo in grupo.subgrupos.all():
                    procedimentos.extend(subgrupo.procedimentos.all())
        else:
            # Se não selecionou nada, pegar todos os procedimentos do perfil
            for grupo in perfil.grupos.all():
                for subgrupo in grupo.subgrupos.all():
                    procedimentos.extend(subgrupo.procedimentos.all())
    
    # Remover duplicatas
    procedimentos = list(set(procedimentos))
    
    # Criar demandas de treinamento
    resultado = criar_demandas_treinamento(colaborador_perfil, procedimentos)
    
    mensagem = f"✅ Colaborador associado ao perfil {perfil.codigo}! "
    if resultado['criados'] > 0:
        mensagem += f"Criadas {resultado['criados']} novas demandas de treinamento. "
    if resultado['ja_existem'] > 0:
        mensagem += f"{resultado['ja_existem']} procedimentos já estavam na matriz."
    
    messages.success(request, mensagem)
    return redirect('detalhe_colaborador', colab_id=colaborador_id)


# ==================== PERFIS DE TREINAMENTO ====================

@login_required
def perfis_list_view(request):
    """Lista todos os perfis de treinamento"""
    perfis = PerfilTreinamento.objects.annotate(
        num_grupos=Count('grupos')
    ).all()
    
    # Filtros
    termo = request.GET.get('q', '').strip()
    ativo = request.GET.get('ativo', '')
    
    if termo:
        perfis = perfis.filter(
            Q(codigo__icontains=termo) | Q(nome__icontains=termo)
        )
    
    if ativo == 'true':
        perfis = perfis.filter(ativo=True)
    elif ativo == 'false':
        perfis = perfis.filter(ativo=False)
    
    perfis = perfis.order_by('codigo')
    
    # Paginação
    paginator = Paginator(perfis, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'perfis': page_obj,
        'termo': termo,
        'ativo': ativo,
        'page_obj': page_obj,
    }
    return render(request, 'procedures/perfil_lista.html', context)


@login_required
def novo_perfil_view(request):
    """Cria um novo perfil de treinamento"""
    if request.method == 'POST':
        form = PerfilTreinamentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil criado com sucesso!')
            return redirect('procedures:perfis_list')
    else:
        form = PerfilTreinamentoForm()
    
    context = {
        'form': form,
        'titulo': 'Novo Perfil de Treinamento'
    }
    return render(request, 'procedures/perfil_form.html', context)


@login_required
def editar_perfil_view(request, perfil_id):
    """Edita um perfil de treinamento existente"""
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    if request.method == 'POST':
        form = PerfilTreinamentoForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil atualizado com sucesso!')
            return redirect('procedures:detalhe_perfil', perfil_id=perfil.id)
    else:
        form = PerfilTreinamentoForm(instance=perfil)
    
    context = {
        'form': form,
        'perfil': perfil,
        'titulo': f'Editar Perfil: {perfil.codigo}'
    }
    return render(request, 'procedures/perfil_form.html', context)


@login_required
def detalhe_perfil_view(request, perfil_id):
    """Exibe os detalhes de um perfil de treinamento"""
    from rh.models import Colaborador
    from organization.models import Setor
    from datetime import date
    
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    # Buscar grupos associados, ordenados por ordem
    grupos = perfil.grupos.prefetch_related('subgrupos').annotate(
        num_subgrupos=Count('subgrupos')
    ).order_by('ordem')
    
    # Buscar colaboradores com este perfil
    colaboradores = ColaboradorPerfil.objects.filter(
        perfil=perfil,
        ativo=True
    ).select_related('colaborador').order_by('colaborador__nome_completo')
    
    # Buscar todos os colaboradores disponíveis (que não tem este perfil ainda)
    colaboradores_com_perfil = colaboradores.values_list('colaborador_id', flat=True)
    todos_colaboradores = Colaborador.objects.exclude(
        id__in=colaboradores_com_perfil
    ).select_related('setor').order_by('nome_completo')
    
    # Buscar todos os setores para o filtro
    setores = Setor.objects.all().order_by('nome')
    
    context = {
        'perfil': perfil,
        'grupos': grupos,
        'colaboradores': colaboradores,
        'todos_colaboradores': todos_colaboradores,
        'setores': setores,
        'today': date.today(),
    }
    return render(request, 'procedures/perfil_detalhe.html', context)


# ==================== GRUPOS DE TREINAMENTO ====================

@login_required
def novo_grupo_view(request, perfil_id):
    """Cria um novo grupo dentro de um perfil"""
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    if request.method == 'POST':
        form = GrupoTreinamentoForm(request.POST)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.perfil = perfil
            grupo.save()
            messages.success(request, 'Grupo criado com sucesso!')
            return redirect('procedures:detalhe_perfil', perfil_id=perfil.id)
    else:
        # Definir próxima ordem automaticamente
        max_ordem = perfil.grupos.aggregate(
            max_ordem=Max('ordem')
        )['max_ordem'] or 0
        form = GrupoTreinamentoForm(initial={'ordem': max_ordem + 1})
    
    context = {
        'form': form,
        'perfil': perfil,
        'titulo': f'Novo Grupo - {perfil.nome}'
    }
    return render(request, 'procedures/grupo_form.html', context)


@login_required
def editar_grupo_view(request, grupo_id):
    """Edita um grupo de treinamento existente"""
    grupo = get_object_or_404(GrupoTreinamento, id=grupo_id)
    
    if request.method == 'POST':
        form = GrupoTreinamentoForm(request.POST, instance=grupo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Grupo atualizado com sucesso!')
            return redirect('procedures:detalhe_perfil', perfil_id=grupo.perfil.id)
    else:
        form = GrupoTreinamentoForm(instance=grupo)
    
    context = {
        'form': form,
        'grupo': grupo,
        'perfil': grupo.perfil,
        'titulo': f'Editar Grupo: {grupo.nome}'
    }
    return render(request, 'procedures/grupo_form.html', context)


@login_required
def deletar_grupo_view(request, grupo_id):
    """Deleta um grupo de treinamento"""
    grupo = get_object_or_404(GrupoTreinamento, id=grupo_id)
    perfil_id = grupo.perfil.id
    
    if request.method == 'POST':
        grupo.delete()
        messages.success(request, 'Grupo deletado com sucesso!')
        return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)
    
    context = {
        'grupo': grupo,
        'perfil': grupo.perfil
    }
    return render(request, 'procedures/grupo_confirma_delete.html', context)


# ==================== SUBGRUPOS DE TREINAMENTO ====================

@login_required
def novo_subgrupo_view(request, grupo_id):
    """Cria um novo subgrupo dentro de um grupo"""
    grupo = get_object_or_404(GrupoTreinamento, id=grupo_id)
    
    if request.method == 'POST':
        form = SubGrupoTreinamentoForm(request.POST)
        if form.is_valid():
            subgrupo = form.save(commit=False)
            subgrupo.grupo = grupo
            subgrupo.save()
            
            # Processar procedimentos do campo hidden
            procedimentos_ids = request.POST.get('procedimentos', '')
            if procedimentos_ids:
                ids_list = [int(id.strip()) for id in procedimentos_ids.split(',') if id.strip().isdigit()]
                from procedures.models import Procedimento
                procedimentos = Procedimento.objects.filter(id__in=ids_list)
                subgrupo.procedimentos.set(procedimentos)
            
            messages.success(request, 'Subgrupo criado com sucesso!')
            return redirect('procedures:detalhe_perfil', perfil_id=grupo.perfil.id)
    else:
        # Definir próxima ordem automaticamente
        max_ordem = grupo.subgrupos.aggregate(
            max_ordem=Max('ordem')
        )['max_ordem'] or 0
        form = SubGrupoTreinamentoForm(initial={'ordem': max_ordem + 1})
    
    context = {
        'form': form,
        'grupo': grupo,
        'perfil': grupo.perfil,
        'titulo': f'Novo Subgrupo - {grupo.nome}'
    }
    return render(request, 'procedures/subgrupo_form.html', context)


@login_required
def editar_subgrupo_view(request, subgrupo_id):
    """Edita um subgrupo de treinamento existente"""
    subgrupo = get_object_or_404(SubGrupoTreinamento, id=subgrupo_id)
    
    if request.method == 'POST':
        form = SubGrupoTreinamentoForm(request.POST, instance=subgrupo)
        if form.is_valid():
            subgrupo = form.save()
            
            # Processar procedimentos do campo hidden
            procedimentos_ids = request.POST.get('procedimentos', '')
            if procedimentos_ids:
                ids_list = [int(id.strip()) for id in procedimentos_ids.split(',') if id.strip().isdigit()]
                from procedures.models import Procedimento
                procedimentos = Procedimento.objects.filter(id__in=ids_list)
                subgrupo.procedimentos.set(procedimentos)
            
            messages.success(request, 'Subgrupo atualizado com sucesso!')
            return redirect('procedures:detalhe_perfil', perfil_id=subgrupo.grupo.perfil.id)
    else:
        form = SubGrupoTreinamentoForm(instance=subgrupo)
    
    context = {
        'form': form,
        'subgrupo': subgrupo,
        'grupo': subgrupo.grupo,
        'perfil': subgrupo.grupo.perfil,
        'titulo': f'Editar Subgrupo: {subgrupo.nome}'
    }
    return render(request, 'procedures/subgrupo_form.html', context)


@login_required
@require_http_methods(["POST"])
def adicionar_procedimento_subgrupo_view(request, subgrupo_id):
    """Adiciona um procedimento ao subgrupo via AJAX"""
    import json
    from django.http import JsonResponse
    from procedures.models import Procedimento
    
    try:
        subgrupo = get_object_or_404(SubGrupoTreinamento, id=subgrupo_id)
        data = json.loads(request.body)
        procedimento_id = data.get('procedimento_id')
        
        procedimento = get_object_or_404(Procedimento, id=procedimento_id)
        subgrupo.procedimentos.add(procedimento)
        
        return JsonResponse({
            'success': True,
            'message': f'Procedimento {procedimento.codigo} adicionado com sucesso!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def remover_procedimento_subgrupo_view(request, subgrupo_id):
    """Remove um procedimento do subgrupo via AJAX"""
    import json
    from django.http import JsonResponse
    from procedures.models import Procedimento
    
    try:
        subgrupo = get_object_or_404(SubGrupoTreinamento, id=subgrupo_id)
        data = json.loads(request.body)
        procedimento_id = data.get('procedimento_id')
        
        procedimento = get_object_or_404(Procedimento, id=procedimento_id)
        subgrupo.procedimentos.remove(procedimento)
        
        return JsonResponse({
            'success': True,
            'message': f'Procedimento {procedimento.codigo} removido com sucesso!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def deletar_subgrupo_view(request, subgrupo_id):
    """Deleta um subgrupo de treinamento"""
    subgrupo = get_object_or_404(SubGrupoTreinamento, id=subgrupo_id)
    perfil_id = subgrupo.grupo.perfil.id
    
    if request.method == 'POST':
        subgrupo.delete()
        messages.success(request, 'Subgrupo deletado com sucesso!')
        return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)
    
    context = {
        'subgrupo': subgrupo,
        'grupo': subgrupo.grupo,
        'perfil': subgrupo.grupo.perfil
    }
    return render(request, 'procedures/subgrupo_confirma_delete.html', context)


# ==================== REORDENAÇÃO ====================

@login_required
def mover_grupo_view(request, grupo_id, direcao):
    """Move um grupo para cima ou para baixo na ordem."""
    grupo = get_object_or_404(GrupoTreinamento, id=grupo_id)
    perfil = grupo.perfil
    
    if direcao == 'cima':
        # Buscar grupo anterior (com ordem menor)
        grupo_anterior = GrupoTreinamento.objects.filter(
            perfil=perfil,
            ordem__lt=grupo.ordem
        ).order_by('-ordem').first()
        
        if grupo_anterior:
            # Trocar ordens
            grupo.ordem, grupo_anterior.ordem = grupo_anterior.ordem, grupo.ordem
            grupo.save()
            grupo_anterior.save()
            messages.success(request, 'Grupo movido para cima!')
    
    elif direcao == 'baixo':
        # Buscar próximo grupo (com ordem maior)
        grupo_posterior = GrupoTreinamento.objects.filter(
            perfil=perfil,
            ordem__gt=grupo.ordem
        ).order_by('ordem').first()
        
        if grupo_posterior:
            # Trocar ordens
            grupo.ordem, grupo_posterior.ordem = grupo_posterior.ordem, grupo.ordem
            grupo.save()
            grupo_posterior.save()
            messages.success(request, 'Grupo movido para baixo!')
    
    return redirect('procedures:detalhe_perfil', perfil_id=perfil.id)


@login_required
def mover_subgrupo_view(request, subgrupo_id, direcao):
    """Move um subgrupo para cima ou para baixo na ordem."""
    subgrupo = get_object_or_404(SubGrupoTreinamento, id=subgrupo_id)
    grupo = subgrupo.grupo
    perfil = grupo.perfil
    
    if direcao == 'cima':
        # Buscar subgrupo anterior (com ordem menor)
        subgrupo_anterior = SubGrupoTreinamento.objects.filter(
            grupo=grupo,
            ordem__lt=subgrupo.ordem
        ).order_by('-ordem').first()
        
        if subgrupo_anterior:
            # Trocar ordens
            subgrupo.ordem, subgrupo_anterior.ordem = subgrupo_anterior.ordem, subgrupo.ordem
            subgrupo.save()
            subgrupo_anterior.save()
            messages.success(request, 'Subgrupo movido para cima!')
    
    elif direcao == 'baixo':
        # Buscar próximo subgrupo (com ordem maior)
        subgrupo_posterior = SubGrupoTreinamento.objects.filter(
            grupo=grupo,
            ordem__gt=subgrupo.ordem
        ).order_by('ordem').first()
        
        if subgrupo_posterior:
            # Trocar ordens
            subgrupo.ordem, subgrupo_posterior.ordem = subgrupo_posterior.ordem, subgrupo.ordem
            subgrupo.save()
            subgrupo_posterior.save()
            messages.success(request, 'Subgrupo movido para baixo!')
    
    return redirect('procedures:detalhe_perfil', perfil_id=perfil.id)


# ==================== ASSOCIAÇÃO COLABORADOR-PERFIL ====================

@login_required
def adicionar_colaborador_perfil_view(request, perfil_id):
    """Adiciona um ou mais colaboradores ao perfil com grupos/subgrupos selecionados"""
    from rh.models import Colaborador
    from datetime import date
    import json
    
    if request.method != 'POST':
        return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)
    
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    colaboradores_ids = request.POST.getlist('colaboradores')  # Múltiplos colaboradores
    grupos_ids = request.POST.getlist('grupos')
    subgrupos_ids = request.POST.getlist('subgrupos')
    data_atribuicao = request.POST.get('data_atribuicao', date.today())
    
    if not colaboradores_ids:
        messages.warning(request, 'Nenhum colaborador foi selecionado.')
        return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)
    
    # Criar estrutura de seleção
    grupos_selecionados = {
        'grupos': [int(g) for g in grupos_ids],
        'subgrupos': [int(s) for s in subgrupos_ids]
    }
    
    adicionados = 0
    ja_existem = []
    erros = []
    total_procedimentos = 0
    total_demandas_criadas = 0
    
    for colaborador_id in colaboradores_ids:
        try:
            colaborador = Colaborador.objects.get(id=colaborador_id)
            
            # Verificar se já existe
            if ColaboradorPerfil.objects.filter(colaborador=colaborador, perfil=perfil).exists():
                ja_existem.append(colaborador.nome_completo)
                continue
            
            # Criar associação
            cp = ColaboradorPerfil.objects.create(
                colaborador=colaborador,
                perfil=perfil,
                grupos_selecionados=grupos_selecionados if grupos_ids or subgrupos_ids else None,
                data_atribuicao=data_atribuicao,
                ativo=True
            )
            
            # Contar procedimentos necessários e criar demandas na matriz
            procedimentos = cp.get_procedimentos_necessarios()
            total_procedimentos += procedimentos.count()
            
            # Sincronizar com matriz de treinamentos - criar registros pendentes
            resultado = criar_demandas_treinamento(cp, procedimentos)
            total_demandas_criadas += resultado['criados']
            
            adicionados += 1
            
        except Colaborador.DoesNotExist:
            erros.append(f'Colaborador ID {colaborador_id} não encontrado')
        except Exception as e:
            erros.append(f'Erro ao adicionar colaborador ID {colaborador_id}: {str(e)}')
    
    # Mensagens de retorno
    if adicionados > 0:
        msg = f'{adicionados} colaborador(es) adicionado(s) ao perfil com sucesso! '
        msg += f'Total de {total_procedimentos} procedimento(s) necessário(s).'
        if total_demandas_criadas > 0:
            msg += f' {total_demandas_criadas} demanda(s) de treinamento criada(s) na matriz.'
        messages.success(request, msg)
    
    if ja_existem:
        messages.warning(
            request,
            f'{len(ja_existem)} colaborador(es) já associado(s): {", ".join(ja_existem[:3])}{"..." if len(ja_existem) > 3 else ""}'
        )
    
    if erros:
        for erro in erros:
            messages.error(request, erro)
    
    return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)


@login_required
@require_http_methods(["POST"])
def remover_colaborador_perfil_view(request, cp_id):
    """Remove um colaborador do perfil via AJAX"""
    from django.http import JsonResponse
    
    try:
        cp = get_object_or_404(ColaboradorPerfil, id=cp_id)
        colaborador_nome = cp.colaborador.nome_completo
        cp.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{colaborador_nome} removido do perfil com sucesso!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
@require_http_methods(["POST"])
def remover_associacao_perfil_colaborador_view(request, colaborador_id, perfil_id):
    """
    Remove a associação entre colaborador e perfil pela página do colaborador.
    Não remove os registros de treinamento, apenas a associação.
    """
    from rh.models import Colaborador
    
    colaborador = get_object_or_404(Colaborador, id=colaborador_id)
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    try:
        cp = ColaboradorPerfil.objects.get(
            colaborador=colaborador,
            perfil=perfil,
            ativo=True
        )
        cp.ativo = False  # Desativa ao invés de deletar para manter histórico
        cp.save()
        
        messages.success(
            request, 
            f"✅ Associação com o perfil {perfil.codigo} removida com sucesso! "
            f"Os registros de treinamento foram mantidos."
        )
    except ColaboradorPerfil.DoesNotExist:
        messages.warning(request, "Associação não encontrada.")
    
    return redirect('detalhe_colaborador', colab_id=colaborador_id)


@login_required
@require_http_methods(["POST"])
def remover_colaboradores_massa_view(request, perfil_id):
    """Remove múltiplos colaboradores do perfil via AJAX"""
    from django.http import JsonResponse
    import json
    
    try:
        perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        if not ids:
            return JsonResponse({
                'success': False,
                'message': 'Nenhum colaborador foi selecionado.'
            }, status=400)
        
        # Buscar e remover
        colaboradores_perfil = ColaboradorPerfil.objects.filter(
            id__in=ids, 
            perfil=perfil
        )
        
        count = colaboradores_perfil.count()
        colaboradores_perfil.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{count} colaborador(es) removido(s) do perfil com sucesso!'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Dados inválidos.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@login_required
def editar_colaborador_perfil_view(request, perfil_id):
    """Edita os grupos/subgrupos de um colaborador no perfil"""
    from rh.models import Colaborador
    from datetime import date
    import json
    
    if request.method != 'POST':
        return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)
    
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    cp_id = request.POST.get('cp_id')
    
    try:
        cp = get_object_or_404(ColaboradorPerfil, id=cp_id, perfil=perfil)
        
        grupos_ids = request.POST.getlist('grupos')
        subgrupos_ids = request.POST.getlist('subgrupos')
        data_atribuicao = request.POST.get('data_atribuicao', date.today())
        subgrupos_ativos_json = request.POST.get('subgrupos_ativos', '{}')
        
        # Atualizar grupos selecionados
        grupos_selecionados = {
            'grupos': [int(g) for g in grupos_ids],
            'subgrupos': [int(s) for s in subgrupos_ids]
        }
        
        cp.grupos_selecionados = grupos_selecionados if grupos_ids or subgrupos_ids else None
        cp.data_atribuicao = data_atribuicao
        cp.save()
        
        # Processar status de ativo/inativo dos subgrupos
        try:
            subgrupos_ativos = json.loads(subgrupos_ativos_json)
        except:
            subgrupos_ativos = {}
        
        # Sincronizar status ativo/inativo com registros de treinamento
        if subgrupos_ativos:
            from procedures.models import RegistroTreinamento
            from procedures.models import SubGrupoTreinamento
            
            # Para cada subgrupo, atualizar o status ativo dos registros associados
            for subgrupo_id, is_ativo in subgrupos_ativos.items():
                try:
                    subgrupo = SubGrupoTreinamento.objects.get(id=int(subgrupo_id))
                    # Obter todos os procedimentos deste subgrupo
                    procedimentos_subgrupo = subgrupo.procedimentos.all()
                    # Atualizar todos os registros de treinamento deste colaborador 
                    # que pertencem aos procedimentos deste subgrupo
                    registros = RegistroTreinamento.objects.filter(
                        colaborador=cp.colaborador,
                        procedimento__in=procedimentos_subgrupo
                    )
                    registros.update(ativo=bool(is_ativo))
                except (SubGrupoTreinamento.DoesNotExist, ValueError):
                    pass
        
        # Recalcular procedimentos necessários
        procedimentos = cp.get_procedimentos_necessarios()
        
        # Sincronizar com matriz de treinamentos - criar novas demandas se necessário
        resultado = criar_demandas_treinamento(cp, procedimentos)
        
        msg = f'Associação de {cp.colaborador.nome_completo} atualizada! '
        msg += f'{procedimentos.count()} procedimento(s) necessário(s).'
        if resultado['criados'] > 0:
            msg += f' {resultado["criados"]} nova(s) demanda(s) de treinamento criada(s).'
        
        messages.success(request, msg)
        
    except Exception as e:
        messages.error(request, f'Erro ao editar colaborador: {str(e)}')
    
    return redirect('procedures:detalhe_perfil', perfil_id=perfil_id)


# ==================== IMPORTAÇÃO EM MASSA ====================

@login_required
def importar_perfis_view(request):
    """Página de importação em massa de perfis de treinamento"""
    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        
        try:
            # Ler Excel
            df = pd.read_excel(arquivo, sheet_name='Perfis')
            
            criados = 0
            erros = []
            
            for index, row in df.iterrows():
                try:
                    # Criar ou atualizar perfil
                    perfil, created = PerfilTreinamento.objects.update_or_create(
                        codigo=str(row['Código Perfil']).strip(),
                        defaults={
                            'nome': str(row['Nome Perfil']).strip(),
                            'descricao': str(row.get('Descrição', '')).strip() if pd.notna(row.get('Descrição')) else '',
                            'ativo': True
                        }
                    )
                    
                    if created:
                        criados += 1
                        
                except Exception as e:
                    erros.append(f"Linha {index + 2}: {str(e)}")
            
            if criados > 0:
                messages.success(request, f'{criados} perfil(s) importado(s) com sucesso!')
            
            if erros:
                for erro in erros[:5]:  # Mostrar apenas os 5 primeiros erros
                    messages.error(request, erro)
                if len(erros) > 5:
                    messages.warning(request, f'... e mais {len(erros) - 5} erro(s).')
                    
        except Exception as e:
            messages.error(request, f'Erro ao processar arquivo: {str(e)}')
    
    return render(request, 'procedures/importar_perfis.html')


@login_required
def importar_estrutura_completa_view(request):
    """Importação completa: Perfis, Grupos, Subgrupos, Procedimentos e Colaboradores"""
    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        
        try:
            from django.db import transaction
            
            # Ler todas as abas
            excel_file = pd.ExcelFile(arquivo)
            
            stats = {
                'perfis': 0,
                'perfis_atualizados': 0,
                'grupos': 0,
                'grupos_atualizados': 0,
                'subgrupos': 0,
                'subgrupos_atualizados': 0,
                'vinculos_procedimentos': 0,
                'vinculos_ja_existentes': 0,
                'colaboradores': 0,
                'colaboradores_ja_associados': 0
            }
            erros = []
            
            # 1. IMPORTAR PERFIS
            if 'Perfis' in excel_file.sheet_names:
                df_perfis = pd.read_excel(excel_file, sheet_name='Perfis')
                for _, row in df_perfis.iterrows():
                    try:
                        perfil, created = PerfilTreinamento.objects.update_or_create(
                            codigo=str(row['Código Perfil']).strip(),
                            defaults={
                                'nome': str(row['Nome Perfil']).strip(),
                                'descricao': str(row.get('Descrição', '')).strip() if pd.notna(row.get('Descrição')) else '',
                                'ativo': True
                            }
                        )
                        if created:
                            stats['perfis'] += 1
                        else:
                            stats['perfis_atualizados'] += 1
                    except Exception as e:
                        erros.append(f"Perfil - Linha {_ + 2}: {str(e)}")
            
            # 2. IMPORTAR GRUPOS
            if 'Grupos' in excel_file.sheet_names:
                df_grupos = pd.read_excel(excel_file, sheet_name='Grupos')
                for _, row in df_grupos.iterrows():
                    try:
                        perfil = PerfilTreinamento.objects.get(codigo=str(row['Código Perfil']).strip())
                        grupo, created = GrupoTreinamento.objects.update_or_create(
                            perfil=perfil,
                            nome=str(row['Nome Grupo']).strip(),
                            defaults={
                                'descricao': str(row.get('Descrição', '')).strip() if pd.notna(row.get('Descrição')) else '',
                                'ordem': int(row.get('Ordem', 1))
                            }
                        )
                        if created:
                            stats['grupos'] += 1
                        else:
                            stats['grupos_atualizados'] += 1
                    except Exception as e:
                        erros.append(f"Grupo - Linha {_ + 2}: {str(e)}")
            
            # 3. IMPORTAR SUBGRUPOS
            if 'Subgrupos' in excel_file.sheet_names:
                df_subgrupos = pd.read_excel(excel_file, sheet_name='Subgrupos')
                for _, row in df_subgrupos.iterrows():
                    try:
                        perfil = PerfilTreinamento.objects.get(codigo=str(row['Código Perfil']).strip())
                        grupo = GrupoTreinamento.objects.get(
                            perfil=perfil,
                            nome=str(row['Nome Grupo']).strip()
                        )
                        subgrupo, created = SubGrupoTreinamento.objects.update_or_create(
                            grupo=grupo,
                            nome=str(row['Nome Subgrupo']).strip(),
                            defaults={
                                'descricao': str(row.get('Descrição', '')).strip() if pd.notna(row.get('Descrição')) else '',
                                'ordem': int(row.get('Ordem', 1))
                            }
                        )
                        if created:
                            stats['subgrupos'] += 1
                        else:
                            stats['subgrupos_atualizados'] += 1
                    except Exception as e:
                        erros.append(f"Subgrupo - Linha {_ + 2}: {str(e)}")
            
            # 4. VINCULAR PROCEDIMENTOS A SUBGRUPOS
            if 'Procedimentos' in excel_file.sheet_names:
                df_procedimentos = pd.read_excel(excel_file, sheet_name='Procedimentos')
                for _, row in df_procedimentos.iterrows():
                    try:
                        codigo_perfil = str(row['Código Perfil']).strip()
                        nome_grupo = str(row['Nome Grupo']).strip()
                        nome_subgrupo = str(row['Nome Subgrupo']).strip()
                        codigo_proc = str(row['Código Procedimento']).strip()
                        
                        perfil = PerfilTreinamento.objects.get(codigo=codigo_perfil)
                        grupo = GrupoTreinamento.objects.get(
                            perfil=perfil,
                            nome=nome_grupo
                        )
                        subgrupo = SubGrupoTreinamento.objects.get(
                            grupo=grupo,
                            nome=nome_subgrupo
                        )
                        
                        # Buscar procedimento pelo código
                        procedimento = Procedimento.objects.filter(codigo=codigo_proc).first()
                        
                        if procedimento:
                            if not subgrupo.procedimentos.filter(id=procedimento.id).exists():
                                subgrupo.procedimentos.add(procedimento)
                                stats['vinculos_procedimentos'] += 1
                            else:
                                stats['vinculos_ja_existentes'] += 1
                        else:
                            erros.append(f"Procedimento {codigo_proc} não encontrado na linha {_ + 2}")
                            
                    except PerfilTreinamento.DoesNotExist:
                        erros.append(f"Vínculo Procedimento - Linha {_ + 2}: Perfil '{row.get('Código Perfil')}' não encontrado")
                    except GrupoTreinamento.DoesNotExist:
                        erros.append(f"Vínculo Procedimento - Linha {_ + 2}: Grupo '{row.get('Nome Grupo')}' não encontrado no perfil '{row.get('Código Perfil')}'")
                    except SubGrupoTreinamento.DoesNotExist:
                        erros.append(f"Vínculo Procedimento - Linha {_ + 2}: Subgrupo '{row.get('Nome Subgrupo')}' não encontrado no grupo '{row.get('Nome Grupo')}'")
                    except Exception as e:
                        erros.append(f"Vínculo Procedimento - Linha {_ + 2}: {str(e)}")
            
            # 5. ASSOCIAR COLABORADORES A PERFIS (com transaction por linha para permitir continuar com erros)
            if 'Colaboradores' in excel_file.sheet_names:
                df_colaboradores = pd.read_excel(excel_file, sheet_name='Colaboradores', dtype={'Matrícula': str})
                from rh.models import Colaborador
                
                # Pré-carregar colaboradores e perfis para evitar N+1 queries
                colaboradores_dict = {c.matricula: c for c in Colaborador.objects.all()}
                perfis_dict = {p.codigo: p for p in PerfilTreinamento.objects.all()}
                
                for _, row in df_colaboradores.iterrows():
                    try:
                        with transaction.atomic():
                            codigo_perfil = str(row['Código Perfil']).strip()
                            if codigo_perfil not in perfis_dict:
                                erros.append(f"Colaborador - Linha {_ + 2}: Perfil '{codigo_perfil}' não encontrado")
                                continue
                            
                            perfil = perfis_dict[codigo_perfil]
                            
                            # Limpar matrícula - remover .0 do pandas e espaços
                            matricula_raw = str(row['Matrícula']).strip()
                            if matricula_raw.endswith('.0'):
                                matricula = matricula_raw[:-2]
                            else:
                                matricula = matricula_raw
                            
                            if matricula not in colaboradores_dict:
                                erros.append(f"Colaborador - Linha {_ + 2}: Matrícula '{matricula}' não encontrada no sistema")
                                continue
                            
                            colaborador = colaboradores_dict[matricula]
                            
                            # Usar get_or_create para evitar duplicatas
                            # Processar grupos/subgrupos selecionados se fornecidos
                            grupos_selecionados = None
                            if pd.notna(row.get('Grupos')) or pd.notna(row.get('Subgrupos')):
                                grupos_ids = []
                                subgrupos_ids = []
                                
                                if pd.notna(row.get('Grupos')):
                                    grupos_nomes = str(row['Grupos']).split(',')
                                    for nome in grupos_nomes:
                                        grupo = GrupoTreinamento.objects.filter(
                                            perfil=perfil,
                                            nome__icontains=nome.strip()
                                        ).first()
                                        if grupo:
                                            grupos_ids.append(grupo.id)
                                
                                if pd.notna(row.get('Subgrupos')):
                                    subgrupos_nomes = str(row['Subgrupos']).split(',')
                                    for nome in subgrupos_nomes:
                                        subgrupo = SubGrupoTreinamento.objects.filter(
                                            grupo__perfil=perfil,
                                            nome__icontains=nome.strip()
                                        ).first()
                                        if subgrupo:
                                            subgrupos_ids.append(subgrupo.id)
                                
                                if grupos_ids or subgrupos_ids:
                                    grupos_selecionados = {
                                        'grupos': grupos_ids,
                                        'subgrupos': subgrupos_ids
                                    }
                            
                            # Criar ou atualizar associação (evita erro de duplicate key)
                            cp, created = ColaboradorPerfil.objects.get_or_create(
                                colaborador=colaborador,
                                perfil=perfil,
                                defaults={
                                    'grupos_selecionados': grupos_selecionados,
                                    'data_atribuicao': datetime.now().date(),
                                    'ativo': True
                                }
                            )
                            
                            if created:
                                # Criar demandas de treinamento apenas se for novo
                                procedimentos = cp.get_procedimentos_necessarios()
                                criar_demandas_treinamento(cp, procedimentos)
                                stats['colaboradores'] += 1
                            else:
                                stats['colaboradores_ja_associados'] += 1
                                    
                    except Exception as e:
                        erros.append(f"Colaborador - Linha {_ + 2}: {str(e)}")
            
            # Mensagens de resultado
            mensagem_parts = []
            
            # Perfis
            if stats['perfis'] > 0 or stats['perfis_atualizados'] > 0:
                msg_perfil = f"Perfis: {stats['perfis']} novos"
                if stats['perfis_atualizados'] > 0:
                    msg_perfil += f", {stats['perfis_atualizados']} atualizados"
                mensagem_parts.append(msg_perfil)
            
            # Grupos
            if stats['grupos'] > 0 or stats['grupos_atualizados'] > 0:
                msg_grupo = f"Grupos: {stats['grupos']} novos"
                if stats['grupos_atualizados'] > 0:
                    msg_grupo += f", {stats['grupos_atualizados']} atualizados"
                mensagem_parts.append(msg_grupo)
            
            # Subgrupos
            if stats['subgrupos'] > 0 or stats['subgrupos_atualizados'] > 0:
                msg_subgrupo = f"Subgrupos: {stats['subgrupos']} novos"
                if stats['subgrupos_atualizados'] > 0:
                    msg_subgrupo += f", {stats['subgrupos_atualizados']} atualizados"
                mensagem_parts.append(msg_subgrupo)
            
            # Vínculos de procedimentos
            if stats['vinculos_procedimentos'] > 0 or stats['vinculos_ja_existentes'] > 0:
                msg_vinculo = f"Vínculos: {stats['vinculos_procedimentos']} novos"
                if stats['vinculos_ja_existentes'] > 0:
                    msg_vinculo += f", {stats['vinculos_ja_existentes']} já existentes"
                mensagem_parts.append(msg_vinculo)
            
            # Colaboradores
            if stats['colaboradores'] > 0 or stats['colaboradores_ja_associados'] > 0:
                msg_colab = f"Colaboradores: {stats['colaboradores']} novos"
                if stats['colaboradores_ja_associados'] > 0:
                    msg_colab += f", {stats['colaboradores_ja_associados']} já associados"
                mensagem_parts.append(msg_colab)
            
            if mensagem_parts:
                mensagem = "✅ Importação concluída! " + " | ".join(mensagem_parts)
                messages.success(request, mensagem)
            else:
                messages.info(request, "Nenhum dado novo foi importado. Todos os registros já existem.")
            
            if erros:
                # Agrupar erros por tipo
                erros_procedimentos = [e for e in erros if 'Procedimento' in e and 'não encontrado' in e]
                erros_subgrupos = [e for e in erros if 'Subgrupo' in e and 'não encontrado' in e]
                erros_colaboradores = [e for e in erros if 'Colaborador' in e and 'Matrícula' in e]
                outros_erros = [e for e in erros if e not in erros_procedimentos + erros_subgrupos + erros_colaboradores]
                
                # Mostrar resumo de erros por tipo
                if erros_procedimentos:
                    procedimentos_unicos = set([e.split(' ')[1] for e in erros_procedimentos if len(e.split(' ')) > 1])
                    msg_proc = f"⚠️ {len(erros_procedimentos)} erro(s) de procedimentos não encontrados: {', '.join(list(procedimentos_unicos)[:5])}"
                    if len(procedimentos_unicos) > 5:
                        msg_proc += f" e mais {len(procedimentos_unicos) - 5}..."
                    messages.warning(request, msg_proc)
                
                if erros_colaboradores:
                    messages.warning(request, f"⚠️ {len(erros_colaboradores)} colaborador(es) não encontrado(s). Verifique as matrículas.")
                
                if erros_subgrupos:
                    messages.warning(request, f"⚠️ {len(erros_subgrupos)} erro(s) de subgrupos não encontrados.")
                
                # Mostrar primeiros erros detalhados
                for erro in (outros_erros + erros_subgrupos[:3] + erros_colaboradores[:3])[:10]:
                    messages.warning(request, erro)
                
                total_mostrado = min(10, len(outros_erros) + min(3, len(erros_subgrupos)) + min(3, len(erros_colaboradores)))
                if len(erros) > total_mostrado:
                    messages.info(request, f"... e mais {len(erros) - total_mostrado} erro(s). Total de erros: {len(erros)}")
                
                # Salvar erros na sessão para possível download
                request.session['erros_importacao'] = erros[:500]  # Limitar a 500 erros
                    
        except Exception as e:
            messages.error(request, f'Erro ao processar arquivo: {str(e)}')
    
    return render(request, 'procedures/importar_estrutura.html')


@login_required
def download_template_importacao_view(request):
    """Gera template Excel para importação"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # ABA 1: Perfis
        df_perfis = pd.DataFrame({
            'Código Perfil': ['PERF001', 'PERF002'],
            'Nome Perfil': ['Operador de Produção', 'Técnico de Qualidade'],
            'Descrição': ['Perfil para operadores da linha de produção', 'Perfil para técnicos do laboratório']
        })
        df_perfis.to_excel(writer, sheet_name='Perfis', index=False)
        
        # ABA 2: Grupos
        df_grupos = pd.DataFrame({
            'Código Perfil': ['PERF001', 'PERF001', 'PERF002'],
            'Nome Grupo': ['Segurança', 'Operacional', 'Metrologia'],
            'Descrição': ['Treinamentos de segurança', 'Procedimentos operacionais', 'Calibração e medição'],
            'Ordem': [1, 2, 1]
        })
        df_grupos.to_excel(writer, sheet_name='Grupos', index=False)
        
        # ABA 3: Subgrupos
        df_subgrupos = pd.DataFrame({
            'Código Perfil': ['PERF001', 'PERF001', 'PERF001'],
            'Nome Grupo': ['Segurança', 'Segurança', 'Operacional'],
            'Nome Subgrupo': ['EPI', 'NR12', 'Setup de Máquina'],
            'Descrição': ['Uso correto de EPIs', 'Norma Regulamentadora 12', 'Procedimentos de setup'],
            'Ordem': [1, 2, 1]
        })
        df_subgrupos.to_excel(writer, sheet_name='Subgrupos', index=False)
        
        # ABA 4: Procedimentos (vínculo com subgrupos)
        df_procedimentos = pd.DataFrame({
            'Código Perfil': ['PERF001', 'PERF001'],
            'Nome Grupo': ['Segurança', 'Operacional'],
            'Nome Subgrupo': ['EPI', 'Setup de Máquina'],
            'Código Procedimento': ['DOC.001', 'DOC.032']
        })
        df_procedimentos.to_excel(writer, sheet_name='Procedimentos', index=False)
        
        # ABA 5: Colaboradores
        df_colaboradores = pd.DataFrame({
            'Código Perfil': ['PERF001', 'PERF002'],
            'Matrícula': ['123', '456'],
            'Grupos': ['Segurança,Operacional', ''],
            'Subgrupos': ['EPI,NR12', '']
        })
        df_colaboradores.to_excel(writer, sheet_name='Colaboradores', index=False)
        
        # ABA 6: Instruções
        instrucoes = pd.DataFrame({
            'INSTRUÇÕES DE PREENCHIMENTO': [
                '1. ABA PERFIS: Liste todos os perfis de treinamento',
                '2. ABA GRUPOS: Defina os grupos dentro de cada perfil',
                '3. ABA SUBGRUPOS: Crie os subgrupos dentro dos grupos',
                '4. ABA PROCEDIMENTOS: Vincule procedimentos (já cadastrados) aos subgrupos',
                '5. ABA COLABORADORES: Associe colaboradores (já cadastrados) aos perfis',
                '',
                'IMPORTANTE:',
                '- Código Perfil deve ser único',
                '- Grupos e Subgrupos devem ter nomes exatos para vinculação',
                '- Procedimentos devem existir previamente no sistema',
                '- Colaboradores devem estar cadastrados (usar matrícula)',
                '- Grupos/Subgrupos na aba Colaboradores são opcionais (separe por vírgula)',
                '- Se não informar Grupos/Subgrupos, o colaborador terá acesso a todos'
            ]
        })
        instrucoes.to_excel(writer, sheet_name='Instruções', index=False)
    
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=template_importacao_perfis.xlsx'
    
    return response


@login_required
def exportar_erros_importacao_view(request):
    """Exporta os erros da última importação para Excel"""
    erros = request.session.get('erros_importacao', [])
    
    if not erros:
        messages.warning(request, 'Nenhum erro de importação encontrado na sessão.')
        return redirect('procedures:importar_estrutura')
    
    output = BytesIO()
    
    # Criar DataFrame com os erros
    df_erros = pd.DataFrame({
        'Erro': erros
    })
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_erros.to_excel(writer, sheet_name='Erros de Importação', index=False)
    
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=erros_importacao_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    # Limpar erros da sessão após exportar
    request.session.pop('erros_importacao', None)
    
    return response

# ==================== MANUTENÇÃO E CORREÇÃO ====================

@login_required
@require_http_methods(["POST"])
def reatribuir_todos_subgrupos_view(request, perfil_id):
    """Reatribui TODOS os subgrupos para TODOS os colaboradores do perfil"""
    from django.http import JsonResponse
    import json
    
    perfil = get_object_or_404(PerfilTreinamento, id=perfil_id)
    
    # Buscar todos os subgrupos do perfil
    todos_subgrupos = SubGrupoTreinamento.objects.filter(
        grupo__perfil=perfil
    ).values_list('id', flat=True)
    
    todos_grupos = GrupoTreinamento.objects.filter(
        perfil=perfil
    ).values_list('id', flat=True)
    
    # Criar estrutura de seleção com TODOS os grupos e subgrupos
    grupos_selecionados = {
        'grupos': list(todos_grupos),
        'subgrupos': list(todos_subgrupos)
    }
    
    # Atualizar TODOS os colaboradores do perfil
    colaboradores = ColaboradorPerfil.objects.filter(
        perfil=perfil,
        ativo=True
    )
    
    total_atualizados = 0
    total_procedimentos_criados = 0
    
    for cp in colaboradores:
        # Atualizar com todos os subgrupos
        cp.grupos_selecionados = grupos_selecionados
        cp.save()
        
        # Recalcular procedimentos necessários
        procedimentos = cp.get_procedimentos_necessarios()
        
        # Criar demandas faltantes
        resultado = criar_demandas_treinamento(cp, procedimentos)
        total_procedimentos_criados += resultado['criados']
        total_atualizados += 1
    
    return JsonResponse({
        'success': True,
        'message': f'✅ {total_atualizados} colaborador(es) reatribuído(s) com todos os {todos_subgrupos.count()} subgrupos. '
                   f'{total_procedimentos_criados} novas demanda(s) de treinamento criada(s).'
    })