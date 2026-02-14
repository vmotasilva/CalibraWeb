from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.db import transaction, IntegrityError
from datetime import date
from django.db.models import Max
from django.db.models import Q
from datetime import datetime
from .models import (
    AcaoCorretiva,
    Solucao,
    TemplateSolucao,
    PlanoAcao,
    SolucaoA3,
    Solucao8D,
    SolucaoRNC,
    SolucaoGestaoDeMudanca,
    RevisaoGerencial
)


@login_required
def listar_templates(request):
    """Lista todos os templates de solução disponíveis"""
    templates = TemplateSolucao.objects.filter(ativo=True).order_by('tipo')
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'acoes/listar_templates.html', context)


@login_required
def download_template(request, template_id):
    """Faz download de um template PDF"""
    template = get_object_or_404(TemplateSolucao, id=template_id, ativo=True)
    
    if template.arquivo_pdf:
        response = FileResponse(template.arquivo_pdf.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="template_{template.get_tipo_display()}.pdf"'
        return response
    
    return JsonResponse({'error': 'Arquivo não encontrado'}, status=404)



@login_required
def listar_solucoes(request):
    """
    Redireciona para listar_acoes (consolidação de URLs)
    /acoes/solucoes/ e /acoes/ apontam para a mesma coisa: 
    Controle de Registros (AcaoCorretiva com dados importados)
    """
    return redirect('acoes:listar_acoes')


@login_required
def criar_plano_acao_modal(request):
    """Cria uma linha de ação do Plano de Ação via modal na tela de detalhes"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    numero_registro = request.POST.get('numero_registro', '').strip()
    solucao_id = request.POST.get('solucao_id')
    input_origem = request.POST.get('input_origem', '').strip()
    kpi = request.POST.get('kpi', '').strip()
    problema = request.POST.get('problema', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    classificacao = request.POST.get('classificacao', '').strip() or None
    status = request.POST.get('status', '').strip() or 'planejada'
    prioridade = request.POST.get('prioridade') == 'on'
    responsaveis_ids = request.POST.getlist('responsaveis_multiplos')
    outros_responsaveis_list = [item.strip() for item in request.POST.getlist('outros_responsaveis') if item.strip()]
    comentarios = request.POST.get('comentarios', '').strip()
    acao_eficaz = request.POST.get('acao_eficaz', '').strip() or None
    data_primeira_deadline = request.POST.get('data_primeira_deadline')
    data_deadline = request.POST.get('data_deadline')
    data_conclusao = request.POST.get('data_conclusao')

    if not solucao_id or not descricao:
        if is_ajax:
            return JsonResponse({'error': 'Campos obrigatórios não preenchidos'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Preencha os campos obrigatórios da ação.')
        if solucao_id:
            return redirect('acoes:detalhe_solucao', solucao_id=solucao_id)
        return redirect('acoes:listar_solucoes')

    # Buscar a solução
    try:
        solucao = Solucao.objects.get(id=solucao_id)
    except Solucao.DoesNotExist:
        if is_ajax:
            return JsonResponse({'error': 'Solução não encontrada'}, status=404)
        from django.contrib import messages
        messages.error(request, 'Solução não encontrada.')
        return redirect('acoes:listar_solucoes')

    # Buscar ou criar PlanoAcao para esta solução
    plano_acao, created = PlanoAcao.objects.get_or_create(
        solucao=solucao,
        defaults={
            'numero_registro': numero_registro,
        }
    )

    # Se já existe e o numero_registro foi fornecido, atualizar
    if not created and numero_registro:
        plano_acao.numero_registro = numero_registro
        plano_acao.save()

    def parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    data_primeira_deadline_parsed = parse_date(data_primeira_deadline)
    data_deadline_parsed = parse_date(data_deadline)
    data_conclusao_parsed = parse_date(data_conclusao)

    responsavel = None
    if responsaveis_ids:
        try:
            from rh.models import Colaborador
            responsavel = Colaborador.objects.filter(id__in=responsaveis_ids).order_by('id').first()
        except Colaborador.DoesNotExist:
            responsavel = None

    numero_acao = request.POST.get('numero_acao')
    try:
        numero_acao = int(numero_acao) if numero_acao else None
    except (TypeError, ValueError):
        numero_acao = None

    if numero_acao is None:
        from acoes.models import LinhaAcao
        numero_max = LinhaAcao.objects.filter(
            plano_acao=plano_acao
        ).aggregate(Max('numero_acao'))['numero_acao__max']
        numero_acao = (numero_max or 0) + 1

    if outros_responsaveis_list:
        outros_responsaveis = ', '.join(outros_responsaveis_list)
        if comentarios:
            comentarios = f"{comentarios}\nOutros responsaveis: {outros_responsaveis}"
        else:
            comentarios = f"Outros responsaveis: {outros_responsaveis}"

    from acoes.models import LinhaAcao
    linha = LinhaAcao.objects.create(
        plano_acao=plano_acao,
        numero_acao=numero_acao,
        input_origem=input_origem or None,
        kpi=kpi or None,
        problema=problema or None,
        descricao=descricao,
        classificacao=classificacao,
        status=status,
        prioridade=prioridade,
        responsavel_acao=responsavel,
        data_primeira_deadline=data_primeira_deadline_parsed,
        data_deadline=data_deadline_parsed,
        comentarios=comentarios or None,
        acao_eficaz=acao_eficaz,
        data_conclusao=data_conclusao_parsed,
    )

    if responsaveis_ids:
        try:
            linha.responsaveis_multiplos.set(responsaveis_ids)
        except Exception:
            pass

    if is_ajax:
        return JsonResponse({'success': True, 'linha_id': linha.id})

    return redirect('acoes:detalhe_solucao', solucao_id=solucao_id)


@login_required
def editar_linha_acao_modal(request, linha_id):
    """Edita uma linha de ação via modal na tela de detalhes"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    from acoes.models import LinhaAcao
    try:
        linha = LinhaAcao.objects.select_related('plano_acao__solucao').get(id=linha_id)
    except LinhaAcao.DoesNotExist:
        if is_ajax:
            return JsonResponse({'error': 'Ação não encontrada'}, status=404)
        from django.contrib import messages
        messages.error(request, 'Ação não encontrada.')
        return redirect('acoes:listar_solucoes')

    solucao_id = request.POST.get('solucao_id') or linha.plano_acao.solucao_id
    input_origem = request.POST.get('input_origem', '').strip()
    kpi = request.POST.get('kpi', '').strip()
    problema = request.POST.get('problema', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    classificacao = request.POST.get('classificacao', '').strip() or None
    status = request.POST.get('status', '').strip() or 'planejada'
    prioridade = request.POST.get('prioridade') == 'on'
    responsaveis_ids = request.POST.getlist('responsaveis_multiplos')
    outros_responsaveis_list = [item.strip() for item in request.POST.getlist('outros_responsaveis') if item.strip()]
    comentarios = request.POST.get('comentarios', '').strip()
    acao_eficaz = request.POST.get('acao_eficaz', '').strip() or None
    data_primeira_deadline = request.POST.get('data_primeira_deadline')
    data_deadline = request.POST.get('data_deadline')
    data_conclusao = request.POST.get('data_conclusao')

    if not descricao:
        if is_ajax:
            return JsonResponse({'error': 'Campos obrigatórios não preenchidos'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Preencha os campos obrigatórios da ação.')
        return redirect('acoes:detalhe_solucao', solucao_id=solucao_id)

    def parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    data_primeira_deadline_parsed = parse_date(data_primeira_deadline)
    data_deadline_parsed = parse_date(data_deadline)
    data_conclusao_parsed = parse_date(data_conclusao)

    responsavel = None
    if responsaveis_ids:
        try:
            from rh.models import Colaborador
            responsavel = Colaborador.objects.filter(id__in=responsaveis_ids).order_by('id').first()
        except Colaborador.DoesNotExist:
            responsavel = None

    if outros_responsaveis_list:
        outros_responsaveis = ', '.join(outros_responsaveis_list)
        if comentarios:
            comentarios = f"{comentarios}\nOutros responsaveis: {outros_responsaveis}"
        else:
            comentarios = f"Outros responsaveis: {outros_responsaveis}"

    linha.input_origem = input_origem or None
    linha.kpi = kpi or None
    linha.problema = problema or None
    linha.descricao = descricao
    linha.classificacao = classificacao
    linha.status = status
    linha.prioridade = prioridade
    linha.responsavel_acao = responsavel
    linha.data_primeira_deadline = data_primeira_deadline_parsed
    linha.data_deadline = data_deadline_parsed
    linha.comentarios = comentarios or None
    linha.acao_eficaz = acao_eficaz
    linha.data_conclusao = data_conclusao_parsed
    linha.save()

    if responsaveis_ids:
        try:
            linha.responsaveis_multiplos.set(responsaveis_ids)
        except Exception:
            pass
    else:
        linha.responsaveis_multiplos.clear()

    if is_ajax:
        return JsonResponse({'success': True, 'linha_id': linha.id})

    return redirect('acoes:detalhe_solucao', solucao_id=solucao_id)


@login_required
def obter_dados_linha_acao(request, pk):
    """Retorna os dados de uma LinhaAcao como JSON para popular o modal de edição"""
    from acoes.models import LinhaAcao
    
    try:
        linha = LinhaAcao.objects.select_related(
            'responsavel_acao', 'plano_acao'
        ).prefetch_related('responsaveis_multiplos').get(id=pk)
    except LinhaAcao.DoesNotExist:
        return JsonResponse({'error': 'Ação não encontrada'}, status=404)
    
    # Responsáveis internos
    responsaveis = []
    for r in linha.responsaveis_multiplos.all():
        responsaveis.append({
            'id': r.id,
            'nome': r.nome_completo
        })
    
    # Responsável principal
    responsavel_principal = None
    if linha.responsavel_acao:
        responsavel_principal = {
            'id': linha.responsavel_acao.id,
            'nome': linha.responsavel_acao.nome_completo
        }
    
    data = {
        'id': linha.id,
        'numero_acao': linha.numero_acao,
        'input_origem': linha.input_origem or '',
        'kpi': linha.kpi or '',
        'classificacao': linha.classificacao or '',
        'problema': linha.problema or '',
        'descricao': linha.descricao or '',
        'status': linha.status or '',
        'prioridade': linha.prioridade,
        'data_primeira_deadline': linha.data_primeira_deadline.strftime('%Y-%m-%d') if linha.data_primeira_deadline else '',
        'data_deadline': linha.data_deadline.strftime('%Y-%m-%d') if linha.data_deadline else '',
        'data_conclusao': linha.data_conclusao.strftime('%Y-%m-%d') if hasattr(linha, 'data_conclusao') and linha.data_conclusao else '',
        'comentarios': linha.comentarios or '',
        'acao_eficaz': linha.acao_eficaz or '',
        'responsaveis_externos': linha.responsaveis_externos or '',
        'responsavel_principal': responsavel_principal,
        'responsaveis': responsaveis,
        'solucao_id': linha.plano_acao.solucao_id if linha.plano_acao else None,
    }
    
    return JsonResponse(data)


@login_required
def detalhe_solucao(request, solucao_id):
    """Mostra detalhes de uma solução"""
    from django.core.exceptions import ObjectDoesNotExist
    
    solucao = get_object_or_404(Solucao, id=solucao_id)
    
    # Carrega a solução específica do tipo
    detalhes = None
    if solucao.tipo == 'plano_acao':
        try:
            detalhes = solucao.plano_acao
        except ObjectDoesNotExist:
            detalhes = None
    elif solucao.tipo == 'a3':
        try:
            detalhes = solucao.a3
        except ObjectDoesNotExist:
            detalhes = None
    elif solucao.tipo == '8d':
        try:
            detalhes = solucao.oito_d
        except ObjectDoesNotExist:
            detalhes = None
    elif solucao.tipo == 'rnc':
        try:
            detalhes = solucao.rnc
        except ObjectDoesNotExist:
            detalhes = None
    elif solucao.tipo == 'gestao_mudanca':
        try:
            detalhes = solucao.gestao_mudanca
        except ObjectDoesNotExist:
            detalhes = None
    elif solucao.tipo == 'revisao_gerencial':
        try:
            detalhes = solucao.revisao_gerencial
        except ObjectDoesNotExist:
            detalhes = None
    
    acoes_plano = None
    linhas_acao = None
    if solucao.tipo == 'plano_acao':
        # Buscar o PlanoAcao associado à solução
        try:
            plano_acao = solucao.plano_acao
            from acoes.models import LinhaAcao
            # Buscar todas as linhas de ação deste plano
            linhas_acao = LinhaAcao.objects.filter(plano_acao=plano_acao).order_by('numero_acao')
            # Mantém acoes_plano para compatibilidade (será uma lista com as linhas)
            acoes_plano = linhas_acao
        except ObjectDoesNotExist:
            pass

    next_numero_acao = 1
    if solucao.tipo == 'plano_acao':
        try:
            plano_acao = solucao.plano_acao
            from acoes.models import LinhaAcao
            numero_max = LinhaAcao.objects.filter(
                plano_acao=plano_acao
            ).aggregate(Max('numero_acao'))['numero_acao__max']
            next_numero_acao = (numero_max or 0) + 1
        except ObjectDoesNotExist:
            next_numero_acao = 1

    try:
        from rh.models import Colaborador
        colaboradores = Colaborador.objects.filter(is_active=True, afastado=False).order_by('nome_completo')
    except Exception:
        colaboradores = []

    try:
        from acoes.models import KPIOpcao
        kpi_opcoes = KPIOpcao.objects.filter(ativo=True).order_by('nome')
    except Exception:
        kpi_opcoes = []

    total_acoes = 0
    acoes_em_curso = 0
    acoes_completas = 0
    acoes_atrasadas = 0
    hoje = date.today()
    if acoes_plano is not None:
        total_acoes = acoes_plano.count()
        for acao in acoes_plano:
            if acao.status == 'em_curso':
                acoes_em_curso += 1
            if acao.status == 'completa':
                acoes_completas += 1
            is_atrasada = bool(
                acao.data_deadline
                and acao.data_deadline < hoje
                and acao.status not in ['completa', 'cancelada']
            )
            acao.is_atrasada = is_atrasada
            if is_atrasada:
                acoes_atrasadas += 1

    context = {
        'solucao': solucao,
        'detalhes': detalhes,
        'acoes_plano': acoes_plano,
        'total_acoes': total_acoes,
        'acoes_em_curso': acoes_em_curso,
        'acoes_completas': acoes_completas,
        'acoes_atrasadas': acoes_atrasadas,
        'hoje': hoje,
        'next_numero_acao': next_numero_acao,
        'colaboradores': colaboradores,
        'kpi_opcoes': kpi_opcoes,
    }
    
    return render(request, 'acoes/detalhe_solucao.html', context)


@login_required
def criar_solucao(request, acao_id):
    """Cria uma nova solução para uma ação corretiva"""
    acao = get_object_or_404(AcaoCorretiva, id=acao_id)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        
        if not tipo or tipo not in [choice[0] for choice in Solucao.TIPO_SOLUCAO_CHOICES]:
            return JsonResponse({'error': 'Tipo de solução inválido'}, status=400)
        
        # Criar solução base
        solucao = Solucao.objects.create(
            acao_corretiva=acao,
            tipo=tipo,
            titulo=request.POST.get('titulo', f'Solução {tipo} para {acao.numero_registro}'),
            descricao=request.POST.get('descricao', ''),
            responsavel_id=request.POST.get('responsavel'),
        )
        
        # Criar solução específica do tipo
        if tipo == 'plano_acao':
            PlanoAcao.objects.create(
                solucao=solucao,
                acao_proposta=request.POST.get('acao_proposta', ''),
                responsavel_acao_id=request.POST.get('responsavel_acao'),
                data_inicio=request.POST.get('data_inicio'),
                data_conclusao=request.POST.get('data_conclusao'),
            )
        elif tipo == 'a3':
            SolucaoA3.objects.create(
                solucao=solucao,
                problema_descricao=request.POST.get('problema_descricao', ''),
                problema_impacto=request.POST.get('problema_impacto', ''),
                situacao_atual=request.POST.get('situacao_atual', ''),
                analise_causas=request.POST.get('analise_causas', ''),
                causa_raiz=request.POST.get('causa_raiz', ''),
                contramedidas=request.POST.get('contramedidas', ''),
                resultados_esperados=request.POST.get('resultados_esperados', ''),
            )
        elif tipo == '8d':
            Solucao8D.objects.create(
                solucao=solucao,
                d1_time=request.POST.get('d1_time', ''),
                d2_descricao=request.POST.get('d2_descricao', ''),
                d2_especificacoes=request.POST.get('d2_especificacoes', ''),
            )
        elif tipo == 'rnc':
            SolucaoRNC.objects.create(
                solucao=solucao,
                nc_descricao=request.POST.get('nc_descricao', ''),
                nc_tipo=request.POST.get('nc_tipo', 'menor'),
                analise_causas=request.POST.get('analise_causas', ''),
                causa_raiz=request.POST.get('causa_raiz', ''),
                acao_imediata=request.POST.get('acao_imediata', ''),
                acao_corretiva=request.POST.get('acao_corretiva_rnc', ''),
                plano_verificacao=request.POST.get('plano_verificacao', ''),
            )
        elif tipo == 'gestao_mudanca':
            SolucaoGestaoDeMudanca.objects.create(
                solucao=solucao,
                mudanca_descricao=request.POST.get('mudanca_descricao', ''),
                motivacao=request.POST.get('motivacao', ''),
                impacto_processos=request.POST.get('impacto_processos', ''),
                plano_implementacao=request.POST.get('plano_implementacao', ''),
                data_implementacao=request.POST.get('data_implementacao'),
            )
        elif tipo == 'revisao_gerencial':
            RevisaoGerencial.objects.create(
                solucao=solucao,
                revisao_descricao=request.POST.get('revisao_descricao', ''),
                escopo=request.POST.get('escopo', ''),
                achados_principais=request.POST.get('achados_principais', ''),
                oportunidades_melhoria=request.POST.get('oportunidades_melhoria', ''),
                recomendacoes=request.POST.get('recomendacoes', ''),
                prioridade_implementacao=request.POST.get('prioridade_implementacao', 'media'),
                plano_acao=request.POST.get('plano_acao', ''),
                data_alvo_implementacao=request.POST.get('data_alvo_implementacao'),
            )
        
        return redirect('acoes:detalhe_solucao', solucao_id=solucao.id)
    
    # Popular selects (responsável, etc.)
    try:
        from rh.models import Colaborador
        colaboradores = Colaborador.objects.filter(afastado=False).order_by('nome_completo')
    except Exception:
        colaboradores = []

    context = {
        'acao': acao,
        'colaboradores': colaboradores,
    }
    
    return render(request, 'acoes/criar_solucao.html', context)


@login_required
def criar_registro_modal(request):
    """Cria um registro e a solução base a partir do modal de listagem"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    tipo = request.POST.get('tipo')
    numero_registro = request.POST.get('numero_registro', '').strip()
    data_abertura = request.POST.get('data_abertura')
    data_vencimento = request.POST.get('data_vencimento')
    unidade = request.POST.get('unidade', '').strip()
    origem = request.POST.get('origem_problema', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    causa_raiz = request.POST.get('causa_raiz', '').strip()
    observacao = request.POST.get('observacao', '').strip()
    link = request.POST.get('link', '').strip()
    responsavel_id = request.POST.get('responsavel')

    if not tipo or tipo not in [choice[0] for choice in Solucao.TIPO_SOLUCAO_CHOICES]:
        if is_ajax:
            return JsonResponse({'error': 'Tipo de solução inválido'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Tipo de solução inválido.')
        return redirect('acoes:listar_solucoes')

    if not numero_registro or not data_abertura or not data_vencimento or not descricao:
        if is_ajax:
            return JsonResponse({'error': 'Campos obrigatórios não preenchidos'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Preencha os campos obrigatórios do registro.')
        return redirect('acoes:listar_solucoes')

    def parse_date(value):
        if not value:
            return None
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None

    data_abertura_parsed = parse_date(data_abertura)
    data_vencimento_parsed = parse_date(data_vencimento)

    if not data_abertura_parsed or not data_vencimento_parsed:
        if is_ajax:
            return JsonResponse({'error': 'Datas inválidas'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Datas inválidas no registro.')
        return redirect('acoes:listar_solucoes')

    responsavel = None
    if responsavel_id:
        try:
            from rh.models import Colaborador
            responsavel = Colaborador.objects.get(id=responsavel_id)
        except Colaborador.DoesNotExist:
            responsavel = None

    criado_por = None
    try:
        from rh.models import Colaborador
        criado_por = Colaborador.objects.get(user_django=request.user)
    except Colaborador.DoesNotExist:
        criado_por = None

    tipo_nome_map = {
        'plano_acao': 'Plano de Ação',
        'a3': 'A3',
        '8d': '8D',
        'rnc': 'RNC',
        'gestao_mudanca': 'Gestão de Mudança',
        'revisao_gerencial': 'Revisão Gerencial',
    }
    titulo_registro = descricao[:80] if descricao else f"Registro {numero_registro}"

    try:
        with transaction.atomic():
            acao = AcaoCorretiva.objects.create(
                numero_registro=numero_registro,
                unidade=unidade or None,
                titulo=titulo_registro,
                descricao=descricao,
                origem=origem or None,
                causa_raiz=causa_raiz or None,
                data_abertura=data_abertura_parsed,
                data_vencimento=data_vencimento_parsed,
                responsavel=responsavel,
                criado_por=criado_por,
                observacoes=observacao or None,
                link_registro=link or None,
                tipo_solucao=tipo,
            )

            solucao = Solucao.objects.create(
                acao_corretiva=acao,
                tipo=tipo,
                titulo=f"{tipo_nome_map.get(tipo, 'Solução')} - {numero_registro}",
                descricao=descricao,
                responsavel=responsavel,
            )

            if tipo == 'plano_acao':
                PlanoAcao.objects.create(
                    solucao=solucao,
                    numero_registro=numero_registro,
                )
            elif tipo == 'a3':
                SolucaoA3.objects.create(
                    solucao=solucao,
                    a3_numero=numero_registro,
                )
            elif tipo == '8d':
                Solucao8D.objects.create(
                    solucao=solucao,
                    numero_formulario=numero_registro,
                )
            elif tipo == 'rnc':
                SolucaoRNC.objects.create(
                    solucao=solucao,
                    numero_rnc=numero_registro,
                    descricao_nc=descricao,
                    causa_raiz=causa_raiz or None,
                    responsavel=responsavel,
                )
            elif tipo == 'gestao_mudanca':
                SolucaoGestaoDeMudanca.objects.create(
                    solucao=solucao,
                    numero_registro=numero_registro,
                    unidade=unidade or None,
                    data_abertura=data_abertura_parsed,
                    observacoes=observacao or None,
                )
            elif tipo == 'revisao_gerencial':
                RevisaoGerencial.objects.create(
                    solucao=solucao,
                    numero_rg=numero_registro,
                    laboratorio=unidade or None,
                )
    except IntegrityError:
        if is_ajax:
            return JsonResponse({'error': 'Número de registro já existe'}, status=400)
        from django.contrib import messages
        messages.error(request, 'Número de registro já existe.')
        return redirect('acoes:listar_solucoes')

    if is_ajax:
        return JsonResponse({'ok': True, 'solucao_id': solucao.id})

    from django.contrib import messages
    messages.success(request, f"Registro '{numero_registro}' criado com sucesso!")
    return redirect('acoes:listar_solucoes')


@login_required
def editar_solucao(request, solucao_id):
    """Edita uma solução existente"""
    solucao = get_object_or_404(Solucao, id=solucao_id)
    
    # Carrega a solução específica do tipo
    if solucao.tipo == 'plano_acao':
        detalhes = solucao.plano_acao
    elif solucao.tipo == 'a3':
        detalhes = solucao.a3
    elif solucao.tipo == '8d':
        detalhes = solucao.oito_d
    elif solucao.tipo == 'rnc':
        detalhes = solucao.rnc
    elif solucao.tipo == 'gestao_mudanca':
        detalhes = solucao.gestao_mudanca
    elif solucao.tipo == 'revisao_gerencial':
        detalhes = solucao.revisao_gerencial
    else:
        detalhes = None
    
    if request.method == 'POST':
        # Atualizar solução base
        solucao.titulo = request.POST.get('titulo', solucao.titulo)
        solucao.descricao = request.POST.get('descricao', solucao.descricao)
        solucao.status = request.POST.get('status', solucao.status)
        if request.POST.get('responsavel'):
            solucao.responsavel_id = request.POST.get('responsavel')
        solucao.save()
        
        # Atualizar solução específica do tipo
        if detalhes:
            # Implementar atualização específica por tipo
            detalhes.save()
        
        return redirect('acoes:detalhe_solucao', solucao_id=solucao.id)
    
    context = {
        'solucao': solucao,
        'detalhes': detalhes,
    }
    
    return render(request, 'acoes/editar_solucao.html', context)
