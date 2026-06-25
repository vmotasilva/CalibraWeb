from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.http import JsonResponse
from datetime import datetime, timedelta

from procedures.models import (
    PlanejamentoTreinamento,
    Procedimento,
    Disciplina,
    DisciplinaProcedimento,
    RegistroTreinamento,
    ListaPresenca,
    AvaliacaoHabilidade,
    PerfilTreinamento,
    MatrizHabilidade,
)
from procedures.forms.forms import PlanejamentoTreinamentoForm
from procedures.views.planejamento_api_demandas import api_demandas_por_perfil_view
from rh.models import Colaborador


# ==================== PLANEJAMENTO DE TREINAMENTOS ====================

@login_required
def planejamentos_list_view(request):
    """Lista todos os planejamentos de treinamento"""
    # Primeiro, atualiza o status de planejamentos que passaram da data
    PlanejamentoTreinamento.objects.exclude(
        status__in=["REALIZADO", "CANCELADO", "ATRASADO"]
    ).filter(
        data_prevista__lt=timezone.now().date()
    ).update(status="ATRASADO")
    
    planejamentos = PlanejamentoTreinamento.objects.select_related(
        'instrutor'
    ).prefetch_related('colaboradores', 'procedimentos').all()
    
    # Filtros
    termo = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    procedimento_id = request.GET.get('procedimento', '')
    mes = request.GET.get('mes', '')
    instrutor_id = request.GET.get('instrutor', '').strip()
    colaborador_id = request.GET.get('colaborador', '').strip()
    
    if termo:
        planejamentos = planejamentos.filter(
            Q(titulo__icontains=termo) | 
            Q(procedimentos__codigo__icontains=termo) |
            Q(procedimentos__nome__icontains=termo)
        ).distinct()
    
    if status:
        status_norm = status.strip().lower()
        if status_norm in {'pendentes', 'pendente', 'abertos', 'aberto', 'abertas', 'aberta'}:
            planejamentos = planejamentos.filter(status__in=['PLANEJADO', 'CONFIRMADO', 'ATRASADO'])
        else:
            planejamentos = planejamentos.filter(status=status)
    
    if procedimento_id:
        planejamentos = planejamentos.filter(procedimentos__id=procedimento_id)
    
    if instrutor_id:
        planejamentos = planejamentos.filter(instrutor_id=instrutor_id)
    
    if colaborador_id:
        planejamentos = planejamentos.filter(colaboradores__id=colaborador_id).distinct()
    
    if mes:
        # Filtrar por mês (formato: YYYY-MM)
        try:
            ano, mes_num = mes.split('-')
            planejamentos = planejamentos.filter(
                data_prevista__year=ano,
                data_prevista__month=mes_num
            )
        except:
            pass
    
    planejamentos = planejamentos.order_by('-data_prevista', '-criado_em')
    
    # Paginação
    paginator = Paginator(planejamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Buscar procedimentos para filtro
    procedimentos = Procedimento.objects.all().order_by('codigo')[:100]
    
    # Buscar instrutores (apenas os que aparecem nos planejamentos)
    instrutor_ids = (
        PlanejamentoTreinamento.objects.exclude(instrutor__isnull=True)
        .values_list('instrutor_id', flat=True)
        .distinct()
    )
    instrutores = (
        Colaborador.objects.filter(id__in=instrutor_ids, is_active=True)
        .distinct()
        .order_by('nome_completo')
    )
    
    # Buscar todos colaboradores para filtro de treinandos
    colaboradores = Colaborador.objects.filter(is_active=True).order_by('nome_completo')[:200]
    
    # Estatísticas
    stats = {
        'total': PlanejamentoTreinamento.objects.count(),
        'planejado': PlanejamentoTreinamento.objects.filter(status='PLANEJADO').count(),
        'confirmado': PlanejamentoTreinamento.objects.filter(status='CONFIRMADO').count(),
        'realizado': PlanejamentoTreinamento.objects.filter(status='REALIZADO').count(),
        'cancelado': PlanejamentoTreinamento.objects.filter(status='CANCELADO').count(),
        'atrasado': PlanejamentoTreinamento.objects.filter(status='ATRASADO').count(),
    }
    
    context = {
        'planejamentos': page_obj,
        'page_obj': page_obj,
        'termo': termo,
        'status': status,
        'procedimento_id': procedimento_id,
        'mes': mes,
        'instrutor_id': instrutor_id,
        'colaborador_id': colaborador_id,
        'procedimentos': procedimentos,
        'instrutores': instrutores,
        'colaboradores': colaboradores,
        'stats': stats,
    }
    return render(request, 'procedures/planejamento_lista.html', context)


@login_required
def selecionar_tipo_planejamento_view(request):
    """Permite ao usuário escolher o tipo de planejamento"""
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        if tipo in ['DEMANDA', 'MATRIZ', 'LIVRE']:
            return redirect('procedures:novo_planejamento_com_tipo', tipo=tipo)
        else:
            messages.error(request, 'Tipo de planejamento inválido.')
    
    context = {
        'tipos_planejamento': [
            {
                'valor': 'DEMANDA',
                'titulo': 'Demanda Existente',
                'descricao': 'Selecione um perfil de colaborador e carregue automaticamente os procedimentos e colaboradores com demandas pendentes.',
                'icone': 'bi-bookmark-check'
            },
            {
                'valor': 'MATRIZ',
                'titulo': 'Matriz de Habilidades',
                'descricao': 'Selecione uma matriz e disciplina para gerar planejamento baseado nas notas dos colaboradores (notas 0 ou 1).',
                'icone': 'bi-grid-3x3-gap'
            },
            {
                'valor': 'LIVRE',
                'titulo': 'Planejamento Livre',
                'descricao': 'Escolha manualmente os procedimentos e colaboradores para o treinamento.',
                'icone': 'bi-pencil-square'
            }
        ]
    }
    
    return render(request, 'procedures/planejamento_tipo_seletor.html', context)


@login_required
def novo_planejamento_view(request, tipo='LIVRE'):
    """Cria um novo planejamento de treinamento baseado no tipo selecionado"""
    # Se tipo for inválido, redirecionar para seletor
    if tipo not in ['DEMANDA', 'MATRIZ', 'LIVRE']:
        return redirect('procedures:selecionar_tipo_planejamento')
    
    if request.method == 'POST':
        # Processar múltiplos procedimentos e colaboradores - usar getlist para múltiplos valores
        procedimentos_ids = request.POST.getlist('procedimentos')
        colaboradores_ids = request.POST.getlist('colaboradores')
        
        form = PlanejamentoTreinamentoForm(request.POST)
        
        # Validar se há colaboradores selecionados
        if not colaboradores_ids:
            messages.error(request, 'Erro ao criar planejamento: Selecione pelo menos um colaborador.')
            context = {
                'form': form,
                'titulo': f'Novo Planejamento de Treinamento',
                'tipo': tipo,
            }
            if tipo == 'DEMANDA':
                context['perfis'] = PerfilTreinamento.objects.all().order_by('nome')
            elif tipo == 'MATRIZ':
                context['matrizes'] = MatrizHabilidade.objects.all().order_by('nome')
                context['disciplinas'] = Disciplina.objects.all().order_by('nome')
            
            template_map = {
                'DEMANDA': 'procedures/planejamento_demanda_form.html',
                'MATRIZ': 'procedures/planejamento_matriz_form.html',
                'LIVRE': 'procedures/planejamento_livre_form.html',
            }
            return render(request, template_map.get(tipo, 'procedures/planejamento_livre_form.html'), context)
        
        if form.is_valid():
            planejamento = form.save(commit=False)
            planejamento.origem = tipo  # Definir origem baseado no tipo selecionado
            planejamento.criado_por = request.user.colaborador if hasattr(request.user, 'colaborador') else None
            # Salvar o instrutor já vem do form
            planejamento.save()
            
            # Adicionar múltiplos procedimentos ao planejamento
            if procedimentos_ids:
                planejamento.procedimentos.set(procedimentos_ids)
            
            # Adicionar múltiplos colaboradores ao planejamento
            if colaboradores_ids:
                planejamento.colaboradores.set(colaboradores_ids)
            
            messages.success(request, f'Planejamento criado com sucesso com {len(procedimentos_ids)} procedimento(s) e {len(colaboradores_ids)} colaborador(es)!')
            return redirect('procedures:detalhe_planejamento', planejamento_id=planejamento.id)
        else:
            # Log dos erros do formulário
            print(f"Form errors: {form.errors}")
            messages.error(request, f'Erro ao criar planejamento. Erros: {form.errors}')
    else:
        form = PlanejamentoTreinamentoForm()
    
    # Definir template baseado no tipo
    template_map = {
        'DEMANDA': 'procedures/planejamento_demanda_form.html',
        'MATRIZ': 'procedures/planejamento_matriz_form.html',
        'LIVRE': 'procedures/planejamento_livre_form.html',
    }
    
    context = {
        'form': form,
        'titulo': f'Novo Planejamento de Treinamento',
        'tipo': tipo,
        'template': template_map.get(tipo, 'procedures/planejamento_livre_form.html')
    }
    
    # Adicionar dados específicos do tipo de planejamento
    if tipo == 'DEMANDA':
        context['perfis'] = PerfilTreinamento.objects.all().order_by('nome')
    elif tipo == 'MATRIZ':
        context['matrizes'] = MatrizHabilidade.objects.all().order_by('nome')
        context['disciplinas'] = Disciplina.objects.all().order_by('nome')
    
    return render(request, template_map.get(tipo, 'procedures/planejamento_livre_form.html'), context)


@login_required
def editar_planejamento_view(request, planejamento_id):
    """Edita um planejamento de treinamento existente"""
    planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
    
    if request.method == 'POST':
        def _normalize_id_list(values):
            normalized = []
            for value in values:
                value = str(value).strip()
                if value.isdigit():
                    normalized.append(value)
            return normalized

        # Processar múltiplos procedimentos/colaboradores (evita limpar M2M com valores vazios)
        procedimentos_posted = 'procedimentos' in request.POST
        colaboradores_posted = 'colaboradores' in request.POST

        procedimentos_ids = _normalize_id_list(request.POST.getlist('procedimentos'))
        colaboradores_ids = _normalize_id_list(request.POST.getlist('colaboradores'))
        
        form = PlanejamentoTreinamentoForm(request.POST, instance=planejamento)
        if form.is_valid():
            # Validar se há colaboradores selecionados (evita zerar a relação no editar)
            if colaboradores_posted and not colaboradores_ids:
                mensagem = 'Selecione pelo menos um colaborador.'
                form.add_error('colaboradores', mensagem)
                messages.error(request, f'Erro ao atualizar planejamento: {mensagem}')
            else:
                planejamento = form.save(commit=False)
                planejamento.save()
                
                # Atualizar procedimentos
                if procedimentos_posted and procedimentos_ids:
                    planejamento.procedimentos.set(procedimentos_ids)

                # Atualizar colaboradores
                if colaboradores_posted and colaboradores_ids:
                    planejamento.colaboradores.set(colaboradores_ids)

                messages.success(request, 'Planejamento atualizado com sucesso!')
                return redirect('procedures:detalhe_planejamento', planejamento_id=planejamento.id)
    else:
        form = PlanejamentoTreinamentoForm(instance=planejamento)
    
    context = {
        'form': form,
        'planejamento': planejamento,
        'titulo': f'Editar Planejamento: {planejamento.titulo}'
    }
    return render(request, 'procedures/planejamento_form.html', context)


@login_required
def detalhe_planejamento_view(request, planejamento_id):
    """Exibe os detalhes de um planejamento de treinamento"""
    planejamento = get_object_or_404(
        PlanejamentoTreinamento.objects.select_related('instrutor')
        .prefetch_related('colaboradores', 'procedimentos'),
        id=planejamento_id
    )
    
    # Verificar registros de treinamento relacionados (para qualquer procedimento do planejamento)
    registros = RegistroTreinamento.objects.filter(
        procedimento__in=planejamento.procedimentos.all(),
        colaborador__in=planejamento.colaboradores.all()
    ).select_related('colaborador', 'procedimento').order_by('-data_treinamento')
    
    # Criar mapeamento (colaborador_id, procedimento_id) -> registro de treinamento mais recente
    registros_dict = {}
    for r in registros:
        key = (r.colaborador_id, r.procedimento_id)
        if key not in registros_dict:
            registros_dict[key] = r
            
    # Preparar lista de colaboradores com status detalhado
    colaboradores_info = []
    treinados_count = 0
    total_procedimentos = planejamento.procedimentos.count()
    
    for colab in planejamento.colaboradores.select_related('setor').all():
        procedimentos_status = []
        quantidade_treinada = 0
        for proc in planejamento.procedimentos.all():
            reg = registros_dict.get((colab.id, proc.id))
            treinado_proc = reg is not None
            if treinado_proc:
                quantidade_treinada += 1
            procedimentos_status.append({
                'procedimento': proc,
                'treinado': treinado_proc,
                'registro': reg
            })
            
        # O colaborador é considerado "Treinado" no planejamento se tiver treinado em todos os procedimentos
        treinado = (quantidade_treinada == total_procedimentos) if total_procedimentos > 0 else False
        if treinado:
            treinados_count += 1
            
        colaboradores_info.append({
            'colaborador': colab,
            'treinado': treinado,
            'quantidade_treinada': quantidade_treinada,
            'total_procedimentos': total_procedimentos,
            'procedimentos_status': procedimentos_status,
        })
    
    pendentes_count = len(colaboradores_info) - treinados_count
    
    context = {
        'planejamento': planejamento,
        'colaboradores_info': colaboradores_info,
        'registros': registros,
        'treinados_count': treinados_count,
        'pendentes_count': pendentes_count,
        'total_colaboradores': len(colaboradores_info),
    }
    return render(request, 'procedures/planejamento_detalhe.html', context)


@login_required
def alterar_status_planejamento_view(request, planejamento_id):
    """Altera o status de um planejamento"""
    planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
    
    if request.method == 'POST':
        novo_status = request.POST.get('status')

        if novo_status == 'REALIZADO':
            messages.info(request, 'Confirme participantes, data, horário e duração para concluir o treinamento.')
            return redirect('procedures:criar_registros_planejamento', planejamento_id=planejamento.id)
        
        if novo_status in ['PLANEJADO', 'CONFIRMADO', 'REALIZADO', 'CANCELADO']:
            planejamento.status = novo_status
            
            # Se for REALIZADO, atualizar data_realizada
            if novo_status == 'REALIZADO' and not planejamento.data_realizada:
                planejamento.data_realizada = timezone.now().date()
            
            planejamento.save()
            messages.success(request, f'Status alterado para {planejamento.get_status_display()}!')
        else:
            messages.error(request, 'Status inválido!')
        
        return redirect('procedures:detalhe_planejamento', planejamento_id=planejamento.id)
    
    context = {
        'planejamento': planejamento
    }
    return render(request, 'procedures/planejamento_alterar_status.html', context)


@login_required
def deletar_planejamento_view(request, planejamento_id):
    """Deleta um planejamento de treinamento"""
    planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
    
    if request.method == 'POST':
        planejamento.delete()
        messages.success(request, 'Planejamento deletado com sucesso!')
        return redirect('procedures:planejamentos_list')
    
    context = {
        'planejamento': planejamento
    }
    return render(request, 'procedures/planejamento_confirma_delete.html', context)


@login_required
def excluir_planejamentos_massa_view(request):
    """Exclui múltiplos planejamentos de uma vez"""
    if request.method == 'POST':
        planejamentos_ids = request.POST.getlist('planejamentos_ids')
        
        if planejamentos_ids:
            # Buscar os planejamentos
            planejamentos = PlanejamentoTreinamento.objects.filter(id__in=planejamentos_ids)
            count = planejamentos.count()
            
            # Excluir
            planejamentos.delete()
            
            messages.success(request, f'{count} planejamento(s) excluído(s) com sucesso!')
        else:
            messages.warning(request, 'Nenhum planejamento foi selecionado.')
        
        return redirect('procedures:planejamentos_list')
    
    # Se não for POST, redirecionar para a lista
    return redirect('procedures:planejamentos_list')


@login_required
def criar_registros_planejamento_view(request, planejamento_id):
    """
    Cria registros de treinamento para todos os colaboradores do planejamento
    Útil quando o treinamento for realizado
    """
    planejamento = get_object_or_404(
        PlanejamentoTreinamento.objects.prefetch_related('colaboradores', 'procedimentos'),
        id=planejamento_id
    )

    planejados_qs = planejamento.colaboradores.all().order_by('nome_completo')
    planejados_ids = set(planejados_qs.values_list('id', flat=True))
    colaboradores_disponiveis = (
        Colaborador.objects.filter(is_active=True)
        .exclude(id__in=planejados_ids)
        .order_by('nome_completo')
    )
    
    if request.method == 'POST':
        data_treinamento_raw = (request.POST.get('data_treinamento') or '').strip()
        horario_realizado_raw = (request.POST.get('horario_realizado') or '').strip()
        duracao_minutos_raw = (request.POST.get('duracao_minutos') or '').strip()

        data_treinamento = parse_date(data_treinamento_raw) if data_treinamento_raw else None
        # Expect datetime-local input (ISO format)
        horario_realizado = datetime.fromisoformat(horario_realizado_raw) if horario_realizado_raw else None

        try:
            duracao_minutos = int(duracao_minutos_raw)
        except (TypeError, ValueError):
            duracao_minutos = None

        participantes_planejados_ids = {
            int(v) for v in request.POST.getlist('participantes_planejados') if str(v).isdigit()
        }
        participantes_adicionais_ids = {
            int(v) for v in request.POST.getlist('participantes_adicionais') if str(v).isdigit()
        }
        participantes_finais_ids = participantes_planejados_ids | participantes_adicionais_ids

        if not data_treinamento:
            messages.error(request, 'Data do treinamento é obrigatória!')
        elif not horario_realizado:
            messages.error(request, 'Horário do treinamento é obrigatório!')
        elif duracao_minutos is None or duracao_minutos <= 0:
            messages.error(request, 'Duração deve ser um número inteiro maior que zero (em minutos).')
        elif not participantes_finais_ids:
            messages.error(request, 'Selecione ao menos um participante para concluir o treinamento.')
        else:
            colaboradores_finais = list(
                Colaborador.objects.filter(id__in=participantes_finais_ids, is_active=True)
            )
            if not colaboradores_finais:
                messages.error(request, 'Nenhum participante válido selecionado.')
                return redirect('procedures:criar_registros_planejamento', planejamento_id=planejamento.id)

            # Atualiza o planejamento com a lista final de participantes.
            planejamento.colaboradores.set([c.id for c in colaboradores_finais])

            # Criar registros para cada colaborador final e cada procedimento
            procedimentos = list(planejamento.procedimentos.all())
            if not procedimentos:
                messages.error(request, 'Não é possível concluir sem procedimentos vinculados ao planejamento.')
                return redirect('procedures:detalhe_planejamento', planejamento_id=planejamento.id)

            observacao_base = (
                f'Treinamento realizado conforme planejamento: {planejamento.titulo} | '
                f'Horário: {horario_realizado.strftime("%H:%M")} | Duração: {duracao_minutos} min'
            )

            with transaction.atomic():
                carga_horaria_horas = round(duracao_minutos / 60, 2)
                hora_fim = (
                    datetime.combine(data_treinamento, horario_realizado.time()) + timedelta(minutes=duracao_minutos)
                ).time()

                observacao_lista_auto = f'Gerada automaticamente a partir do planejamento #{planejamento.id}.'
                lista_presenca = ListaPresenca.objects.filter(
                    data_sessao=data_treinamento,
                    observacoes=observacao_lista_auto,
                ).order_by('-id').first()

                # Cria automaticamente uma lista de presença da sessão realizada.
                if not lista_presenca:
                    lista_presenca = ListaPresenca.objects.create(
                        titulo=planejamento.titulo,
                        instrutor=planejamento.instrutor,
                        instrutor_nome=planejamento.instrutor.nome_completo if planejamento.instrutor else '',
                        data_sessao=data_treinamento,
                        hora_inicio=horario_realizado.time(),
                        hora_fim=hora_fim,
                        carga_horaria=carga_horaria_horas,
                        local=planejamento.local,
                        observacoes=observacao_lista_auto,
                        criado_por=request.user,
                    )

                registros_criados = 0
                for colaborador in colaboradores_finais:
                    for procedimento in procedimentos:
                        registro, criado = RegistroTreinamento.objects.get_or_create(
                            procedimento=procedimento,
                            colaborador=colaborador,
                            data_treinamento=data_treinamento,
                            defaults={
                                'observacoes': observacao_base,
                                'lista_presenca': lista_presenca,
                            },
                        )

                        if criado:
                            registros_criados += 1
                            continue

                        update_fields = []
                        if registro.lista_presenca_id != lista_presenca.id:
                            registro.lista_presenca = lista_presenca
                            update_fields.append('lista_presenca')
                        if not registro.observacoes:
                            registro.observacoes = observacao_base
                            update_fields.append('observacoes')
                        if update_fields:
                            registro.save(update_fields=update_fields)

                planejamento.status = 'REALIZADO'
                planejamento.data_realizada = data_treinamento
                planejamento.horario_previsto = horario_realizado
                planejamento.carga_horaria = duracao_minutos
                planejamento.save(update_fields=['status', 'data_realizada', 'horario_previsto', 'carga_horaria', 'atualizado_em'])

            messages.success(
                request,
                f'{registros_criados} registros criados. Participantes confirmados: {len(colaboradores_finais)}. '
                f'Lista de presença gerada: {lista_presenca.codigo}.',
            )
            return redirect('procedures:detalhe_planejamento', planejamento_id=planejamento.id)

        return redirect('procedures:criar_registros_planejamento', planejamento_id=planejamento.id)
    
    context = {
        'planejamento': planejamento,
        'participantes_planejados': planejados_qs,
        'participantes_adicionais': colaboradores_disponiveis,
    }
    return render(request, 'procedures/planejamento_criar_registros.html', context)


# ==================== GERAÇÃO DE PLANEJAMENTOS A PARTIR DA MATRIZ ====================

@login_required
def selecionar_matriz_view(request):
    """
    Exibe tela para selecionar matriz de habilidades para gerar planejamentos
    """
    from procedures.models import MatrizHabilidade
    
    matrizes = MatrizHabilidade.objects.all()
    
    context = {
        'matrizes': matrizes,
        'titulo': 'Gerar Planejamentos pela Matriz de Habilidades'
    }
    return render(request, 'procedures/selecionar_matriz.html', context)


@login_required
def gerar_planejamentos_matriz_view(request, matriz_id):
    """
    Gera planejamentos automaticamente baseado em disciplinas da matriz 
    com avaliação abaixo de 2 (exceto -1 que é N/A)
    """
    from procedures.models import MatrizHabilidade
    from django.db.models import Q
    
    matriz = get_object_or_404(MatrizHabilidade, id=matriz_id)
    
    if request.method == 'POST':
        disciplina_id = request.POST.get('disciplina')
        data_prevista = request.POST.get('data_prevista')
        local = request.POST.get('local', '')
        
        if not disciplina_id or not data_prevista:
            messages.error(request, 'Disciplina e data são obrigatórias!')
            return redirect('procedures:gerar_planejamentos_matriz', matriz_id=matriz_id)
        
        try:
            disciplina = Disciplina.objects.get(id=disciplina_id, matriz=matriz)
        except Disciplina.DoesNotExist:
            messages.error(request, 'Disciplina não encontrada!')
            return redirect('procedures:gerar_planejamentos_matriz', matriz_id=matriz_id)
        
        # Buscar colaboradores com avaliação abaixo de 2 nesta disciplina
        avaliacoes = AvaliacaoHabilidade.objects.filter(
            disciplina=disciplina,
            nivel__lt=2,  # Menor que 2
            nivel__gte=0  # Não é -1 (N/A)
        ).select_related('colaborador')
        
        planejamentos_criados = []
        for avaliacao in avaliacoes:
            # Buscar procedimentos associados a essa disciplina
            procedimentos = Procedimento.objects.filter(
                disciplinas_associadas__disciplina=disciplina
            ).distinct()
            
            if not procedimentos.exists():
                continue
            
            # Verificar se já existe planejamento ativo para este colaborador e disciplina
            planejamento_existe = PlanejamentoTreinamento.objects.filter(
                origem='MATRIZ',
                disciplina=disciplina,
                colaboradores=avaliacao.colaborador,
                status__in=['PLANEJADO', 'CONFIRMADO']
            ).exists()
            
            if not planejamento_existe:
                # Criar UM planejamento com MÚLTIPLOS procedimentos
                planejamento = PlanejamentoTreinamento.objects.create(
                    titulo=f'{disciplina.nome} - {avaliacao.colaborador.nome_completo}',
                    origem='MATRIZ',
                    disciplina=disciplina,
                    data_prevista=data_prevista,
                    local=local,
                    status='PLANEJADO',
                    observacoes=f'Gerado automaticamente da Matriz de Habilidades.\n'
                                f'Avaliação da disciplina: {avaliacao.get_nivel_display()}\n'
                                f'Colaborador: {avaliacao.colaborador.nome_completo}'
                )
                # Adicionar todos os procedimentos da disciplina
                planejamento.procedimentos.set(procedimentos)
                planejamento.colaboradores.add(avaliacao.colaborador)
                planejamentos_criados.append(planejamento)
        
        if planejamentos_criados:
            messages.success(
                request, 
                f'{len(planejamentos_criados)} planejamentos criados com sucesso a partir da matriz!'
            )
        else:
            messages.info(
                request,
                'Nenhum novo planejamento foi criado (podem já existir planejamentos para esses colaboradores e procedimentos).'
            )
        
        return redirect('procedures:planejamentos_list')
    
    # GET - Exibir formulário
    disciplinas = Disciplina.objects.filter(
        matriz=matriz,
        ativo=True
    ).order_by('codigo')
    
    # Para cada disciplina, contar quantos colaboradores têm avaliação abaixo de 2
    disciplinas_com_gaps = []
    for disciplina in disciplinas:
        colaboradores_gap = AvaliacaoHabilidade.objects.filter(
            disciplina=disciplina,
            nivel__lt=2,
            nivel__gte=0
        ).values_list('colaborador_id', flat=True).distinct()
        
        if colaboradores_gap.count() > 0:
            disciplinas_com_gaps.append({
                'disciplina': disciplina,
                'gaps_count': colaboradores_gap.count()
            })
    
    context = {
        'matriz': matriz,
        'disciplinas': disciplinas_com_gaps,
        'titulo': f'Gerar Planejamentos - {matriz.nome}'
    }
    return render(request, 'procedures/gerar_planejamentos_matriz.html', context)


# ==================== API ENDPOINTS ====================

@login_required
def api_procedimentos_filtros_view(request):
    """
    Endpoint JSON para buscar procedimentos com filtros
    Parâmetros GET:
    - q: busca por palavra-chave (código ou nome)
    - matriz: filtrar por matriz
    - sub_area: filtrar por sub-área
    """
    procedimentos = Procedimento.objects.all()
    
    # Filtro por palavra-chave
    busca = request.GET.get('q', '').strip()
    if busca:
        procedimentos = procedimentos.filter(
            Q(codigo__icontains=busca) | 
            Q(nome__icontains=busca) |
            Q(descricao__icontains=busca)
        )
    
    # Filtro por matriz
    matriz = request.GET.get('matriz', '').strip()
    if matriz:
        procedimentos = procedimentos.filter(matriz__icontains=matriz)
    
    # Filtro por sub-área
    sub_area = request.GET.get('sub_area', '').strip()
    if sub_area:
        procedimentos = procedimentos.filter(sub_area__icontains=sub_area)
    
    # Limitar resultados e ordenar
    procedimentos = procedimentos.distinct().order_by('codigo')[:100]
    
    # Debug - Log dos filtros aplicados
    print(f"[DEBUG] Filtros: q='{busca}', matriz='{matriz}', sub_area='{sub_area}'")
    print(f"[DEBUG] Total de procedimentos encontrados: {procedimentos.count()}")
    
    # Serializar para JSON
    data = {
        'procedimentos': [
            {
                'id': p.id,
                'codigo': p.codigo or '',
                'nome': p.nome or '',
                'matriz': p.matriz or '',
                'sub_area': p.sub_area or '',
                'descricao': p.descricao[:100] if p.descricao else ''
            }
            for p in procedimentos
        ]
    }
    
    return JsonResponse(data)


@login_required
def api_matrizes_list_view(request):
    """Endpoint JSON que retorna lista de matrizes únicas"""
    matrizes = Procedimento.objects.exclude(
        matriz__isnull=True
    ).exclude(
        matriz=''
    ).values_list('matriz', flat=True).distinct().order_by('matriz')
    
    data = {
        'matrizes': list(matrizes)
    }
    
    return JsonResponse(data)


@login_required
def api_subgrupos_list_view(request):
    """Endpoint JSON que retorna lista de sub-áreas únicas dos procedimentos"""
    matriz = request.GET.get('matriz', '').strip()
    
    # Buscar sub-áreas
    procedimentos = Procedimento.objects.exclude(
        sub_area__isnull=True
    ).exclude(
        sub_area=''
    )
    
    # Filtrar por matriz se fornecida
    if matriz:
        procedimentos = procedimentos.filter(matriz__icontains=matriz)
    
    # Obter sub-áreas únicas
    sub_areas = procedimentos.values_list('sub_area', flat=True).distinct().order_by('sub_area')
    
    # Debug
    print(f"[DEBUG API SUB-AREAS] Matriz filtro: '{matriz}'")
    print(f"[DEBUG API SUB-AREAS] Total procedimentos: {procedimentos.count()}")
    print(f"[DEBUG API SUB-AREAS] Sub-áreas encontradas: {list(sub_areas)}")
    
    data = {
        'sub_areas': [{'id': sa, 'nome': sa} for sa in sub_areas if sa]
    }
    
    return JsonResponse(data)


@login_required
def adicionar_procedimento_planejamento(request, planejamento_id):
    """Adiciona procedimento(s) ao planejamento via AJAX"""
    if request.method == 'POST':
        planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
        procedimento_ids = request.POST.getlist('procedimento_ids')
        
        if procedimento_ids:
            planejamento.procedimentos.add(*procedimento_ids)
            return JsonResponse({
                'success': True,
                'message': f'{len(procedimento_ids)} procedimento(s) adicionado(s) com sucesso!'
            })
        return JsonResponse({'success': False, 'message': 'Nenhum procedimento selecionado'})
    return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)


@login_required
def remover_procedimento_planejamento(request, planejamento_id, procedimento_id):
    """Remove procedimento do planejamento via AJAX"""
    if request.method == 'POST':
        planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
        procedimento = get_object_or_404(Procedimento, id=procedimento_id)
        
        planejamento.procedimentos.remove(procedimento)
        return JsonResponse({
            'success': True,
            'message': 'Procedimento removido com sucesso!'
        })
    return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)


@login_required
def adicionar_colaborador_planejamento(request, planejamento_id):
    """Adiciona colaborador(es) ao planejamento via AJAX"""
    if request.method == 'POST':
        planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
        colaborador_ids = request.POST.getlist('colaborador_ids')
        
        if colaborador_ids:
            planejamento.colaboradores.add(*colaborador_ids)
            return JsonResponse({
                'success': True,
                'message': f'{len(colaborador_ids)} colaborador(es) adicionado(s) com sucesso!'
            })
        return JsonResponse({'success': False, 'message': 'Nenhum colaborador selecionado'})
    return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)


@login_required
def remover_colaborador_planejamento(request, planejamento_id, colaborador_id):
    """Remove colaborador do planejamento via AJAX"""
    if request.method == 'POST':
        planejamento = get_object_or_404(PlanejamentoTreinamento, id=planejamento_id)
        from rh.models import Colaborador
        colaborador = get_object_or_404(Colaborador, id=colaborador_id)
        
        planejamento.colaboradores.remove(colaborador)
        return JsonResponse({
            'success': True,
            'message': 'Colaborador removido com sucesso!'
        })
    return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)


# ==============================================================================
# APIS PARA MATRIZ DE HABILIDADES (Novo Fluxo)
# ==============================================================================

@login_required
def api_disciplinas_por_matriz_view(request):
    """
    Endpoint JSON para buscar disciplinas de uma matriz específica
    Parâmetros GET:
    - matriz_id: ID da matriz
    """
    from procedures.models import MatrizHabilidade
    
    matriz_id = request.GET.get('matriz_id', '').strip()
    
    if not matriz_id:
        return JsonResponse({'disciplinas': []})
    
    try:
        matriz = MatrizHabilidade.objects.get(id=matriz_id)
        disciplinas = matriz.disciplinas_matriz.filter(ativo=True).values('id', 'codigo', 'nome').order_by('codigo')
        
        data = {
            'disciplinas': list(disciplinas)
        }
        return JsonResponse(data)
    except MatrizHabilidade.DoesNotExist:
        return JsonResponse({'disciplinas': [], 'error': 'Matriz não encontrada'})


@login_required
def api_matrizes_bd_view(request):
    """
    Endpoint JSON que retorna lista de matrizes do banco de dados
    """
    from procedures.models import MatrizHabilidade
    
    matrizes = MatrizHabilidade.objects.filter(ativo=True).values('id', 'codigo', 'nome').order_by('codigo')
    
    data = {
        'matrizes': list(matrizes)
    }
    return JsonResponse(data)


@login_required
def api_procedimentos_por_disciplina_view(request):
    """
    Endpoint JSON para buscar procedimentos associados a uma disciplina
    Parâmetros GET:
    - disciplina_id: ID da disciplina
    
    Tenta buscar de múltiplas formas:
    1. Via DisciplinaProcedimento (relação explícita)
    2. Fallback: Procedimentos com nomes/códigos similares
    3. Fallback: Procedimentos da mesma matriz
    """
    from procedures.models import DisciplinaProcedimento
    
    disciplina_id = request.GET.get('disciplina_id', '').strip()
    
    if not disciplina_id:
        return JsonResponse({'procedimentos': []})
    
    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
        
        # ESTRATÉGIA 1: Buscar via DisciplinaProcedimento (relação explícita)
        print(f"\n[DEBUG API] ===== BUSCANDO PROCEDIMENTOS PARA DISCIPLINA =====")
        print(f"[DEBUG API] Disciplina ID: {disciplina.id}, Nome: {disciplina.nome}, Código: {disciplina.codigo}")
        
        procedimentos_qs = DisciplinaProcedimento.objects.filter(
            disciplina_id=disciplina.id
        ).select_related('procedimento').order_by('ordem')
        
        procedimentos_list = []
        for dp in procedimentos_qs:
            procedimentos_list.append({
                'id': dp.procedimento.id,
                'codigo': dp.procedimento.codigo or '',
                'nome': dp.procedimento.nome or '',
                'matriz': dp.procedimento.matriz or '',
                'sub_area': dp.procedimento.sub_area or ''
            })
        
        print(f"[DEBUG API] Estratégia 1 (DisciplinaProcedimento): {len(procedimentos_list)} encontrados")
        
        # ESTRATÉGIA 2: Se não encontrou, procurar por nome/código similares
        if not procedimentos_list:
            print(f"[DEBUG API] Estratégia 1 falhou, tentando estratégia 2...")
            
            # Extrair palavras-chave da disciplina
            termos = disciplina.nome.lower().split()
            print(f"[DEBUG API] Termos para busca: {termos}")
            
            # Procurar procedimentos que correspondem
            query = Q()
            for termo in termos:
                if len(termo) > 2:  # Ignorar palavras muito curtas
                    query |= Q(nome__icontains=termo) | Q(codigo__icontains=termo)
            
            query_procedimentos = Procedimento.objects.filter(query).distinct()[:50]
            print(f"[DEBUG API] Encontrados por similaridade: {query_procedimentos.count()}")
            
            procedimentos_list = [
                {
                    'id': p.id,
                    'codigo': p.codigo or '',
                    'nome': p.nome or '',
                    'matriz': p.matriz or '',
                    'sub_area': p.sub_area or ''
                }
                for p in query_procedimentos.order_by('codigo')
            ]
        
        # ESTRATÉGIA 3: Se ainda não encontrou e tem matriz, procurar por matriz
        if not procedimentos_list and disciplina.matriz:
            print(f"[DEBUG API] Estratégia 2 falhou, tentando estratégia 3 (por matriz)...")
            
            query_procedimentos = Procedimento.objects.filter(
                Q(nome__icontains=disciplina.nome) |
                Q(codigo__icontains=disciplina.codigo) |
                Q(nome__icontains=disciplina.matriz.nome)
            ).distinct()[:50]
            
            print(f"[DEBUG API] Encontrados por matriz: {query_procedimentos.count()}")
            
            procedimentos_list = [
                {
                    'id': p.id,
                    'codigo': p.codigo or '',
                    'nome': p.nome or '',
                    'matriz': p.matriz or '',
                    'sub_area': p.sub_area or ''
                }
                for p in query_procedimentos.order_by('codigo')
            ]
        
        print(f"[DEBUG API] TOTAL PROCEDIMENTOS CARREGADOS: {len(procedimentos_list)}")
        
        data = {
            'procedimentos': procedimentos_list,
            'debug': {
                'disciplina_id': disciplina.id,
                'disciplina_nome': disciplina.nome,
                'disciplina_codigo': disciplina.codigo,
                'total': len(procedimentos_list),
                'estrategia_usada': '1-DisciplinaProcedimento' if len(procedimentos_list) > 0 else '2-Similaridade ou 3-Matriz'
            }
        }
        return JsonResponse(data)
        
    except Disciplina.DoesNotExist:
        print(f"[DEBUG API] Disciplina não encontrada")
        return JsonResponse({'procedimentos': [], 'error': 'Disciplina não encontrada'})


@login_required
def api_debug_disciplina_view(request):
    """
    Endpoint de DEBUG para verificar dados de uma disciplina
    Mostra: procedimentos associados, total de procedimentos no sistema, etc.
    Parâmetros GET:
    - disciplina_id: ID da disciplina
    """
    from procedures.models import DisciplinaProcedimento
    
    disciplina_id = request.GET.get('disciplina_id', '').strip()
    
    if not disciplina_id:
        return JsonResponse({'error': 'disciplina_id é obrigatório'})
    
    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
        
        # Contar associações de procedimentos
        total_associacoes = DisciplinaProcedimento.objects.filter(disciplina=disciplina).count()
        associacoes = list(
            DisciplinaProcedimento.objects.filter(disciplina=disciplina).values_list(
                'procedimento__id',
                'procedimento__codigo',
                'procedimento__nome'
            )
        )
        
        # Total de procedimentos no sistema
        total_procedimentos = Procedimento.objects.count()
        
        data = {
            'disciplina': {
                'id': disciplina.id,
                'codigo': disciplina.codigo,
                'nome': disciplina.nome,
                'matriz_id': disciplina.matriz.id if disciplina.matriz else None,
                'matriz_nome': disciplina.matriz.nome if disciplina.matriz else None,
            },
            'procedimentos_associados': {
                'total': total_associacoes,
                'lista': [
                    {
                        'id': a[0],
                        'codigo': a[1],
                        'nome': a[2]
                    }
                    for a in associacoes
                ]
            },
            'sistema': {
                'total_procedimentos': total_procedimentos,
                'aviso': 'Se procedimentos_associados.total = 0, você precisa criar as associações em DisciplinaProcedimento'
            }
        }
        
        return JsonResponse(data)
        
    except Disciplina.DoesNotExist:
        return JsonResponse({'error': 'Disciplina não encontrada'})


@login_required
def api_colaboradores_por_disciplina_view(request):
    """
    Endpoint JSON para buscar colaboradores com avaliações em uma disciplina
    Descarta colaboradores com nível -1 (N/A)
    Parâmetros GET:
    - disciplina_id: ID da disciplina
    """
    disciplina_id = request.GET.get('disciplina_id', '').strip()
    
    if not disciplina_id:
        return JsonResponse({'colaboradores': []})
    
    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
        
        # Buscar avaliações da disciplina, excluindo N/A (-1)
        avaliacoes = AvaliacaoHabilidade.objects.filter(
            disciplina=disciplina,
            nivel__gte=0  # Excluir -1 (N/A)
        ).select_related('colaborador').order_by('colaborador__nome_completo')
        
        # Formatar resposta com dados do colaborador e sua avaliação
        dados_colaboradores = [
            {
                'id': av.colaborador.id,
                'nome': av.colaborador.nome_completo,
                'matricula': av.colaborador.matricula or '-',
                'setor': av.colaborador.setor.nome if av.colaborador.setor else '-',
                'nivel_competencia': av.nivel,
                'nivel_label': dict(AvaliacaoHabilidade.NIVEIS).get(av.nivel, 'Desconhecido'),
                'data_avaliacao': av.data_avaliacao.strftime('%d/%m/%Y') if av.data_avaliacao else '-'
            }
            for av in avaliacoes
        ]
        
        data = {
            'colaboradores': dados_colaboradores
        }
        return JsonResponse(data)
    except Disciplina.DoesNotExist:
        return JsonResponse({'colaboradores': [], 'error': 'Disciplina não encontrada'})

@login_required
def api_areas_list_view(request):
    """Endpoint JSON que retorna lista de áreas/sub-áreas únicas"""
    areas = Procedimento.objects.exclude(
        sub_area__isnull=True
    ).exclude(
        sub_area=''
    ).values_list('sub_area', flat=True).distinct().order_by('sub_area')
    
    data = {
        'areas': list(areas)
    }
    
    return JsonResponse(data)


# ==================== EXPORT PARA EXCEL ====================

@login_required
def exportar_lista_planejamentos_excel_view(request):
    """Exporta lista de planejamentos (com filtros aplicados) para Excel"""
    from procedures.utils.export_utils import PlanejamentoExcelExporter
    
    # Replicar a mesma lógica de filtro da view de lista
    planejamentos = PlanejamentoTreinamento.objects.select_related(
        'instrutor'
    ).prefetch_related('colaboradores', 'procedimentos').all()
    
    # Aplicar os mesmos filtros da lista
    termo = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    procedimento_id = request.GET.get('procedimento', '')
    mes = request.GET.get('mes', '')
    instrutor_id = request.GET.get('instrutor', '').strip()
    colaborador_id = request.GET.get('colaborador', '').strip()
    
    if termo:
        planejamentos = planejamentos.filter(
            Q(titulo__icontains=termo) | 
            Q(procedimentos__codigo__icontains=termo) |
            Q(procedimentos__nome__icontains=termo)
        ).distinct()
    
    if status:
        planejamentos = planejamentos.filter(status=status)
    
    if procedimento_id:
        planejamentos = planejamentos.filter(procedimentos__id=procedimento_id)
    
    if instrutor_id:
        planejamentos = planejamentos.filter(instrutor_id=instrutor_id)
    
    if colaborador_id:
        planejamentos = planejamentos.filter(colaboradores__id=colaborador_id).distinct()
    
    if mes:
        try:
            ano, mes_num = mes.split('-')
            planejamentos = planejamentos.filter(
                data_prevista__year=ano,
                data_prevista__month=mes_num
            )
        except:
            pass
    
    planejamentos = planejamentos.order_by('-data_prevista', '-criado_em')
    
    # Gerar Excel
    exporter = PlanejamentoExcelExporter()
    return exporter.export_lista_planejamentos(planejamentos)


@login_required
def exportar_detalhe_planejamento_excel_view(request, planejamento_id):
    """Exporta detalhes de um planejamento específico para Excel (múltiplas abas)"""
    from procedures.utils.export_utils import PlanejamentoExcelExporter
    
    planejamento = get_object_or_404(
        PlanejamentoTreinamento.objects.select_related('instrutor')
        .prefetch_related('colaboradores', 'procedimentos'),
        id=planejamento_id
    )
    
    exporter = PlanejamentoExcelExporter()
    return exporter.export_detalhe_planejamento(planejamento)