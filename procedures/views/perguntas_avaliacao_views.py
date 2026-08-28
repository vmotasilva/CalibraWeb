# -*- coding: utf-8 -*-
"""
Views para Gerenciamento de Perguntas de Auto-Avaliação de Procedimentos Críticos (FOR.141).
Permite configurar as 5 perguntas técnicas (ordem 1 a 5) por Procedimento e testar a geração do formulário Excel.
"""

from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from procedures.models import Procedimento, PerguntaAvaliacao, MatrizHabilidade
from procedures.services.treinamento_excel_export_service import gerar_auto_avaliacao_for141_xlsx


# Perguntas padrão sugeridas pelo SGQ / ISO 9001
PERGUNTAS_PADRAO_SGQ = [
    "Qual o objetivo principal deste procedimento operacional e quais os impactos de eventuais não conformidades no processo?",
    "Quais os equipamentos de proteção individual (EPIs), ferramentas e requisitos de segurança obrigatórios para esta atividade?",
    "Descreva a sequência padrão de execução das etapas e os principais parâmetros operacionais a serem rigorosamente controlados.",
    "Quais são os pontos críticos de controle (PCC), tolerâncias permitidas e critérios de aceitação do produto/serviço?",
    "Em caso de desvio, defeito ou falha identificada durante a operação, qual é o fluxo correto de contenção e comunicação imediata?"
]


@login_required
def perguntas_avaliacao_list_view(request):
    """
    Tela principal para visualização e gerenciamento de perguntas de autoavaliação (1 a 5)
    associadas aos procedimentos (com ênfase em Procedimentos Críticos).
    """
    busca = request.GET.get('busca', '').strip()
    criticidade_filtro = request.GET.get('criticidade', 'CRITICO') # Padrão: Procedimentos Críticos
    matriz_filtro = request.GET.get('matriz', '')
    status_filtro = request.GET.get('status', '')

    qs = Procedimento.objects.prefetch_related('perguntas_avaliacao').all()

    if criticidade_filtro and criticidade_filtro != 'TODOS':
        qs = qs.filter(criticidade=criticidade_filtro)

    if matriz_filtro:
        qs = qs.filter(matriz=matriz_filtro)

    if busca:
        qs = qs.filter(
            Q(codigo__icontains=busca) |
            Q(nome__icontains=busca) |
            Q(sub_area__icontains=busca) |
            Q(matriz__icontains=busca)
        )

    # Ordenar por código
    qs = qs.order_by('codigo')

    # Métricas gerais
    total_procedimentos_criticos = Procedimento.objects.filter(criticidade='CRITICO').count()
    
    # Processar contagens de perguntas por procedimento
    procedimentos_processados = []
    total_completos = 0
    total_parciais = 0
    total_sem_perguntas = 0

    for proc in qs:
        perguntas_ativas = list(proc.perguntas_avaliacao.filter(ativo=True).order_by('ordem'))
        qtd = len(perguntas_ativas)
        
        if qtd == 5:
            total_completos += 1
            status_calc = 'COMPLETO'
        elif qtd > 0:
            total_parciais += 1
            status_calc = 'PARCIAL'
        else:
            total_sem_perguntas += 1
            status_calc = 'PENDENTE'

        if status_filtro and status_filtro != status_calc:
            continue

        procedimentos_processados.append({
            'procedimento': proc,
            'perguntas': perguntas_ativas,
            'qtd_perguntas': qtd,
            'status': status_calc,
            'perguntas_display': [
                next((p for p in perguntas_ativas if p.ordem == i), None) for i in range(1, 6)
            ]
        })

    # Paginação
    page = request.GET.get('page', 1)
    paginator = Paginator(procedimentos_processados, 20)
    try:
        procedimentos_paginados = paginator.page(page)
    except PageNotAnInteger:
        procedimentos_paginados = paginator.page(1)
    except EmptyPage:
        procedimentos_paginados = paginator.page(paginator.num_pages)

    # Lista de Matrizes únicas para o filtro
    matrizes_disponiveis = Procedimento.objects.exclude(matriz__isnull=True).exclude(matriz='').values_list('matriz', flat=True).distinct().order_by('matriz')

    context = {
        'procedimentos_page': procedimentos_paginados,
        'total_criticos': total_procedimentos_criticos,
        'total_completos': total_completos,
        'total_parciais': total_parciais,
        'total_sem_perguntas': total_sem_perguntas,
        'busca': busca,
        'criticidade_filtro': criticidade_filtro,
        'matriz_filtro': matriz_filtro,
        'status_filtro': status_filtro,
        'matrizes_disponiveis': matrizes_disponiveis,
        'perguntas_padrao_sgq': PERGUNTAS_PADRAO_SGQ,
    }
    return render(request, 'procedures/perguntas_avaliacao_lista.html', context)


@login_required
@require_GET
def obter_perguntas_procedimento_api(request, procedimento_id):
    """
    API JSON para retornar as perguntas cadastradas de um procedimento (ordem 1 a 5).
    """
    proc = get_object_or_404(Procedimento, id=procedimento_id)
    perguntas = PerguntaAvaliacao.objects.filter(procedimento=proc, ativo=True).order_by('ordem')

    perguntas_data = []
    perguntas_map = {p.ordem: p for p in perguntas}

    for ordem in range(1, 6):
        p = perguntas_map.get(ordem)
        perguntas_data.append({
            'ordem': ordem,
            'enunciado': p.enunciado if p else '',
            'resposta_esperada': p.resposta_esperada if (p and p.resposta_esperada) else '',
            'id': p.id if p else None,
        })

    return JsonResponse({
        'success': True,
        'procedimento': {
            'id': proc.id,
            'codigo': proc.codigo,
            'nome': proc.nome,
            'criticidade': proc.criticidade,
            'matriz': proc.matriz or '-',
            'sub_area': proc.sub_area or '-',
        },
        'perguntas': perguntas_data,
        'sugestoes_padrao': PERGUNTAS_PADRAO_SGQ,
    })


@login_required
@require_POST
def salvar_perguntas_procedimento_api(request, procedimento_id):
    """
    API JSON para salvar / atualizar as 5 perguntas de autoavaliação de um procedimento.
    """
    proc = get_object_or_404(Procedimento, id=procedimento_id)

    try:
        perguntas_salvas = []
        for ordem in range(1, 6):
            enunciado = request.POST.get(f'pergunta_{ordem}', '').strip()
            resposta_esperada = request.POST.get(f'resposta_{ordem}', '').strip()

            if enunciado:
                obj, created = PerguntaAvaliacao.objects.update_or_create(
                    procedimento=proc,
                    ordem=ordem,
                    defaults={
                        'enunciado': enunciado,
                        'resposta_esperada': resposta_esperada or None,
                        'ativo': True,
                    }
                )
                perguntas_salvas.append(obj.ordem)
            else:
                # Se o enunciado foi limpo, exclui a pergunta daquela ordem
                PerguntaAvaliacao.objects.filter(procedimento=proc, ordem=ordem).delete()

        return JsonResponse({
            'success': True,
            'message': f"Perguntas de autoavaliação do procedimento {proc.codigo} salvas com sucesso!",
            'total_perguntas': len(perguntas_salvas),
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=400)


@login_required
def exportar_preview_for141_procedimento_view(request, procedimento_id):
    """
    Gera uma pré-visualização para download do FOR.141.r02 (.xlsx) preenchido
    diretamente com as 5 perguntas configuradas para este procedimento.
    """
    proc = get_object_or_404(Procedimento, id=procedimento_id)

    from procedures.models import PlanejamentoTreinamento

    # Criar um objeto de planejamento virtual para renderizar o FOR.141
    plan_mock = PlanejamentoTreinamento(
        titulo=f"Autoavaliação Técnica - {proc.codigo}",
        data_prevista=date.today(),
        status="PLANEJADO",
        carga_horaria=60,
    )
    setattr(plan_mock, '_mock_procs', [proc])

    try:
        excel_buffer = gerar_auto_avaliacao_for141_xlsx(plan_mock)
    except Exception as e:
        messages.error(request, f"Erro ao gerar visualização do FOR.141: {str(e)}")
        return redirect('procedures:perguntas_avaliacao_list')

    filename = f"FOR.141.r02_Preview_{proc.codigo.replace('/', '_')}.xlsx"
    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Access-Control-Expose-Headers"] = "Content-Disposition"
    return response


@login_required
def exportar_preview_for141_pdf_procedimento_view(request, procedimento_id):
    """
    Gera o PDF oficial (FOR.141.r02) preenchido diretamente com as 5 perguntas deste procedimento.
    """
    proc = get_object_or_404(Procedimento, id=procedimento_id)

    from procedures.models import PlanejamentoTreinamento
    from procedures.services.auto_avaliacao_pdf_service import gerar_auto_avaliacao_pdf

    plan_mock = PlanejamentoTreinamento(
        titulo=f"Autoavaliação Técnica - {proc.codigo}",
        data_prevista=date.today(),
        status="PLANEJADO",
        carga_horaria=60,
    )
    setattr(plan_mock, '_mock_procs', [proc])

    try:
        pdf_buffer = gerar_auto_avaliacao_pdf(plan_mock)
    except Exception as e:
        messages.error(request, f"Erro ao gerar PDF do FOR.141: {str(e)}")
        return redirect('procedures:perguntas_avaliacao_list')

    filename = f"FOR.141.r02_Preview_{proc.codigo.replace('/', '_')}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Access-Control-Expose-Headers"] = "Content-Disposition"
    return response


@login_required
def preview_for141_print_procedimento_view(request, procedimento_id):
    """
    Renderiza a tela de visualização e impressão direta (FOR.141.r02) para este procedimento.
    """
    proc = get_object_or_404(Procedimento, id=procedimento_id)

    from procedures.models import PlanejamentoTreinamento
    from procedures.services.treinamento_excel_export_service import _obter_perguntas_treinamento

    plan_mock = PlanejamentoTreinamento(
        titulo=f"Autoavaliação Técnica - {proc.codigo}",
        data_prevista=date.today(),
        status="PLANEJADO",
        carga_horaria=60,
    )
    setattr(plan_mock, '_mock_procs', [proc])

    perguntas_raw = _obter_perguntas_treinamento(plan_mock)
    perguntas_lista = []
    for i in range(5):
        txt = perguntas_raw[i] if i < len(perguntas_raw) and perguntas_raw[i] else f"Critério operacional e controle técnico {i+1} do procedimento."
        perguntas_lista.append({'numero': i+1, 'texto': txt})

    d_colab = {
        'nome': 'COLABORADOR EXEMPLO / EM AVALIAÇÃO',
        'matricula': 'MAT-0000',
        'setor': proc.sub_area or proc.matriz or 'OPERAÇÃO / QUALIDADE',
        'cargo': 'OPERADOR / TÉCNICO',
        'gestor': 'RESPONSÁVEL TÉCNICO',
    }

    return render(request, 'procedures/auto_avaliacao_print.html', {
        'planejamento': plan_mock,
        'colaborador_selecionado': None,
        'd_colab': d_colab,
        'perguntas_lista': perguntas_lista,
        'proc_str': f"{proc.codigo} - {proc.nome}",
        'instrutor_nome': "INSTRUTOR QUALIFICADO",
        'data_str': date.today().strftime("%d/%m/%Y"),
    })

