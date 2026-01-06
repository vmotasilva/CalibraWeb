from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from procedures.models import MatrizHabilidade, Disciplina, DisciplinaProcedimento, AvaliacaoHabilidade, GrupoTreinamento, SubGrupoTreinamento, Procedimento
from rh.models import Colaborador


@login_required
def api_disciplinas_por_matriz_view(request):
    """
    Endpoint JSON para buscar disciplinas de uma matriz
    
    Parâmetros GET:
    - matriz_id: ID da matriz
    """
    matriz_id = request.GET.get('matriz_id', '').strip()
    
    if not matriz_id:
        return JsonResponse({
            'disciplinas': [],
            'error': 'matriz_id é obrigatório'
        })
    
    try:
        matriz = MatrizHabilidade.objects.get(id=matriz_id)
        
        # Buscar disciplinas da matriz
        disciplinas = matriz.disciplinas_matriz.all().order_by('nome')
        
        disciplinas_list = [
            {
                'id': disc.id,
                'nome': disc.nome,
            }
            for disc in disciplinas
        ]
        
        data = {
            'matriz_nome': matriz.nome,
            'disciplinas': disciplinas_list,
            'total_disciplinas': len(disciplinas_list)
        }
        
        return JsonResponse(data)
    except MatrizHabilidade.DoesNotExist:
        return JsonResponse({
            'disciplinas': [],
            'error': 'Matriz não encontrada'
        })


@login_required
def api_procedimentos_por_disciplina_view(request):
    """
    Endpoint JSON para buscar procedimentos de uma disciplina
    
    Parâmetros GET:
    - disciplina_id: ID da disciplina
    """
    disciplina_id = request.GET.get('disciplina_id', '').strip()
    
    if not disciplina_id:
        return JsonResponse({
            'procedimentos': [],
            'error': 'disciplina_id é obrigatório'
        })
    
    try:
        disciplina = Disciplina.objects.get(id=disciplina_id)
        
        # Buscar procedimentos da disciplina
        procedimentos_disciplina = DisciplinaProcedimento.objects.filter(
            disciplina=disciplina
        ).select_related('procedimento').order_by('ordem')
        
        procedimentos = [
            {
                'id': dp.procedimento.id,
                'codigo': dp.procedimento.codigo,
                'nome': dp.procedimento.nome,
            }
            for dp in procedimentos_disciplina
        ]
        
        data = {
            'disciplina_nome': disciplina.nome,
            'procedimentos': procedimentos,
            'total_procedimentos': len(procedimentos)
        }
        
        return JsonResponse(data)
    except Disciplina.DoesNotExist:
        return JsonResponse({
            'procedimentos': [],
            'error': 'Disciplina não encontrada'
        })


@login_required
def api_colaboradores_por_matriz_view(request):
    """
    Endpoint JSON para buscar colaboradores de uma matriz com notas baixas (0 ou 1)
    
    Parâmetros GET:
    - matriz_id: ID da matriz
    - disciplina_id: ID da disciplina (opcional, para filtrar por disciplina)
    """
    matriz_id = request.GET.get('matriz_id', '').strip()
    disciplina_id = request.GET.get('disciplina_id', '').strip()
    
    if not matriz_id:
        return JsonResponse({
            'colaboradores': [],
            'error': 'matriz_id é obrigatório'
        })
    
    try:
        matriz = MatrizHabilidade.objects.get(id=matriz_id)
        
        # Buscar todos os colaboradores que têm essa matriz
        # A relação é através de ColaboradorMatrizHabilidade com related_name "matrizes_habilidade"
        colaboradores_matriz = Colaborador.objects.filter(
            matrizes_habilidade__matriz__id=matriz_id,
            is_active=True
        ).distinct()
        
        colaboradores_filtrados = []
        
        for colab in colaboradores_matriz:
            notas = {}
            
            if disciplina_id:
                # Buscar nota específica da disciplina
                try:
                    disciplina = Disciplina.objects.get(id=disciplina_id)
                    avaliacao = AvaliacaoHabilidade.objects.filter(
                        colaborador=colab,
                        matriz=matriz,
                        disciplina=disciplina
                    ).first()
                    
                    nota = avaliacao.nivel if avaliacao else None
                except Disciplina.DoesNotExist:
                    nota = None
                
                # Incluir se: nota é 0 ou 1, ou não tem avaliação (None)
                if nota is None or nota in [0, 1]:
                    colaboradores_filtrados.append({
                        'id': colab.id,
                        'nome': colab.nome_completo,
                        'matricula': colab.matricula or '-',
                        'setor': colab.setor.nome if colab.setor else '-',
                        'nota': nota,
                        'nota_descricao': dict(AvaliacaoHabilidade.NIVEIS).get(nota, 'Sem avaliação') if nota is not None else 'Sem avaliação'
                    })
            else:
                # Buscar todas as notas da matriz para esse colaborador
                avaliacoes = AvaliacaoHabilidade.objects.filter(
                    colaborador=colab,
                    matriz=matriz
                )
                
                tem_nota_baixa = False
                tem_sem_avaliacao = False
                
                # Verificar se tem nota 0 ou 1 em alguma disciplina
                for av in avaliacoes:
                    if av.nivel in [0, 1]:
                        tem_nota_baixa = True
                        break
                
                # Se não tem nota baixa, verificar se tem disciplinas sem avaliação
                if not tem_nota_baixa:
                    disciplinas_matriz = matriz.disciplinas.all()
                    for disc in disciplinas_matriz:
                        if not AvaliacaoHabilidade.objects.filter(
                            colaborador=colab,
                            matriz=matriz,
                            disciplina=disc
                        ).exists():
                            tem_sem_avaliacao = True
                            break
                
                # Incluir se tem nota baixa ou tem sem avaliação
                if tem_nota_baixa or tem_sem_avaliacao:
                    colaboradores_filtrados.append({
                        'id': colab.id,
                        'nome': colab.nome_completo,
                        'matricula': colab.matricula or '-',
                        'setor': colab.setor.nome if colab.setor else '-',
                        'status': 'Nota Baixa' if tem_nota_baixa else 'Sem Avaliação'
                    })
        
        data = {
            'matriz_nome': matriz.nome,
            'colaboradores': colaboradores_filtrados,
            'total_colaboradores': len(colaboradores_filtrados)
        }
        
        return JsonResponse(data)
    except MatrizHabilidade.DoesNotExist:
        return JsonResponse({
            'colaboradores': [],
            'error': 'Matriz não encontrada'
        })


@login_required
def api_procedimentos_buscar_view(request):
    """
    Endpoint JSON para buscar procedimentos com filtros
    
    Parâmetros GET:
    - grupo_nome: Nome do grupo (opcional)
    - subgrupo_nome: Nome do sub-grupo (opcional)
    - search: Busca por código ou nome (opcional)
    """
    grupo_nome = request.GET.get('grupo_nome', '').strip()
    subgrupo_nome = request.GET.get('subgrupo_nome', '').strip()
    search = request.GET.get('search', '').strip()
    
    try:
        # Começar com todos os procedimentos
        procedimentos = Procedimento.objects.all()
        
        # Se houver filtro de subgrupo, use o relacionamento M2M
        if subgrupo_nome:
            procedimentos = procedimentos.filter(subgrupos_treinamento__nome=subgrupo_nome)
        elif grupo_nome:
            # Se houver filtro de grupo, buscar os sub-grupos desse grupo
            procedimentos = procedimentos.filter(subgrupos_treinamento__grupo__nome=grupo_nome)
        
        # Busca por código ou nome
        if search:
            procedimentos = procedimentos.filter(
                Q(codigo__icontains=search) | Q(nome__icontains=search)
            )
        
        # Remover duplicatas e ordenar
        procedimentos = procedimentos.distinct().order_by('codigo')
        
        procedimentos_list = []
        for proc in procedimentos:
            # Buscar o primeiro sub-grupo e grupo associados
            subgrupos = proc.subgrupos_treinamento.all()
            
            grupo_nome_proc = '-'
            subgrupo_nome_proc = '-'
            
            if subgrupos.exists():
                subgrupo_obj = subgrupos.first()
                subgrupo_nome_proc = subgrupo_obj.nome
                grupo_nome_proc = subgrupo_obj.grupo.nome if subgrupo_obj.grupo else '-'
            
            procedimentos_list.append({
                'id': proc.id,
                'codigo': proc.codigo or '-',
                'nome': proc.nome or '-',
                'grupo_nome': grupo_nome_proc,
                'subgrupo_nome': subgrupo_nome_proc,
            })
        
        data = {
            'procedimentos': procedimentos_list,
            'total': len(procedimentos_list)
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({
            'procedimentos': [],
            'error': str(e)
        })


@login_required
def api_colaboradores_buscar_view(request):
    """
    Endpoint JSON para buscar colaboradores com filtros
    
    Parâmetros GET:
    - turno: Turno (ADM, DIURNO, NOTURNO, etc.) (opcional)
    - setor_id: ID do setor (opcional)
    - lider_id: ID do líder (opcional)
    - supervisor_id: ID do supervisor (opcional)
    - search: Busca por nome ou matrícula (opcional)
    - ativo: Apenas colaboradores ativos (default: true) (opcional)
    """
    turno = request.GET.get('turno', '').strip()
    setor_id = request.GET.get('setor_id', '').strip()
    lider_id = request.GET.get('lider_id', '').strip()
    supervisor_id = request.GET.get('supervisor_id', '').strip()
    search = request.GET.get('search', '').strip()
    ativo = request.GET.get('ativo', 'true').lower() == 'true'
    
    try:
        colaboradores = Colaborador.objects.filter(is_active=ativo)
        
        # Filtrar por turno
        if turno:
            colaboradores = colaboradores.filter(turno=turno)
        
        # Filtrar por setor
        if setor_id:
            colaboradores = colaboradores.filter(setor_id=setor_id)
        
        # Filtrar por líder
        if lider_id:
            colaboradores = colaboradores.filter(lider_id=lider_id)
        
        # Filtrar por supervisor
        if supervisor_id:
            colaboradores = colaboradores.filter(supervisor_id=supervisor_id)
        
        # Busca por nome ou matrícula
        if search:
            colaboradores = colaboradores.filter(
                Q(nome_completo__icontains=search) | Q(matricula__icontains=search)
            )
        
        colaboradores = colaboradores.order_by('nome_completo')
        
        colaboradores_list = [
            {
                'id': colab.id,
                'nome': colab.nome_completo,
                'matricula': colab.matricula,
                'cargo': colab.cargo or '-',
                'turno': colab.turno or '-',
                'setor': colab.setor.nome if colab.setor else '-',
                'setor_id': colab.setor.id if colab.setor else None,
                'lider': colab.lider.nome_completo if colab.lider else '-',
                'lider_id': colab.lider.id if colab.lider else None,
                'supervisor': colab.supervisor.nome_completo if colab.supervisor else '-',
                'supervisor_id': colab.supervisor.id if colab.supervisor else None,
            }
            for colab in colaboradores
        ]
        
        # Coletar valores únicos para os filtros
        todos_turnos = Colaborador.objects.filter(is_active=ativo).values_list('turno', flat=True).distinct()
        todos_setores = list(Colaborador.objects.filter(is_active=ativo).values('setor__id', 'setor__nome').distinct())
        todos_lideres = list(Colaborador.objects.filter(is_active=ativo, lider__isnull=False).values('lider__id', 'lider__nome_completo').distinct())
        todos_supervisores = list(Colaborador.objects.filter(is_active=ativo, supervisor__isnull=False).values('supervisor__id', 'supervisor__nome_completo').distinct())
        
        data = {
            'colaboradores': colaboradores_list,
            'total': len(colaboradores_list),
            'filtros': {
                'turnos': [t for t in todos_turnos if t],
                'setores': [{'id': s['setor__id'], 'nome': s['setor__nome']} for s in todos_setores if s['setor__id']],
                'lideres': [{'id': l['lider__id'], 'nome': l['lider__nome_completo']} for l in todos_lideres if l['lider__id']],
                'supervisores': [{'id': s['supervisor__id'], 'nome': s['supervisor__nome_completo']} for s in todos_supervisores if s['supervisor__id']],
            }
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({
            'colaboradores': [],
            'filtros': {},
            'error': str(e)
        })
