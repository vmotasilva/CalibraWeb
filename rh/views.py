from django.http import JsonResponse
from django.db.models import Q
from rh.models import Colaborador
from organization.models import Setor
from django.contrib.auth.decorators import login_required


def api_colaboradores(request):
    """API para buscar colaboradores com filtros"""
    colaboradores = Colaborador.objects.select_related('setor', 'lider', 'supervisor').all()
    
    # Aplicar filtros
    q = request.GET.get('q', '').strip()
    if q:
        colaboradores = colaboradores.filter(
            Q(nome_completo__icontains=q) |
            Q(matricula__icontains=q)
        )
    
    setor_id = request.GET.get('setor', '').strip()
    if setor_id:
        colaboradores = colaboradores.filter(setor_id=setor_id)
    
    cargo = request.GET.get('cargo', '').strip()
    if cargo:
        colaboradores = colaboradores.filter(cargo__icontains=cargo)
    
    grupo = request.GET.get('grupo', '').strip()
    if grupo:
        colaboradores = colaboradores.filter(grupo__icontains=grupo)
    
    turno = request.GET.get('turno', '').strip()
    if turno:
        colaboradores = colaboradores.filter(turno=turno)
    
    lider_id = request.GET.get('lider', '').strip()
    if lider_id:
        colaboradores = colaboradores.filter(lider_id=lider_id)
    
    supervisor_id = request.GET.get('supervisor', '').strip()
    if supervisor_id:
        colaboradores = colaboradores.filter(supervisor_id=supervisor_id)
    
    # Limitar resultado
    colaboradores = colaboradores.order_by('nome_completo')[:200]
    
    # Formatar resposta
    data = {
        'colaboradores': [
            {
                'id': c.id,
                'nome': c.nome_completo,
                'matricula': c.matricula,
                'cargo': c.cargo or '',
                'setor': c.setor.nome if c.setor else '',
                'grupo': c.grupo or '',
                'turno': c.get_turno_display() if c.turno else '',
            }
            for c in colaboradores
        ]
    }
    
    return JsonResponse(data)


def api_setores(request):
    """API para listar setores"""
    setores = Setor.objects.all().order_by('nome')
    
    data = {
        'setores': [
            {
                'id': s.id,
                'nome': s.nome
            }
            for s in setores
        ]
    }
    
    return JsonResponse(data)


def api_cargos(request):
    """API para listar cargos únicos"""
    cargos = Colaborador.objects.exclude(
        cargo__isnull=True
    ).exclude(
        cargo=''
    ).values_list('cargo', flat=True).distinct().order_by('cargo')
    
    data = {
        'cargos': list(cargos)
    }
    
    return JsonResponse(data)


def api_grupos(request):
    """API para listar grupos únicos"""
    grupos = Colaborador.objects.exclude(
        grupo__isnull=True
    ).exclude(
        grupo=''
    ).values_list('grupo', flat=True).distinct().order_by('grupo')
    
    data = {
        'grupos': list(grupos)
    }
    
    return JsonResponse(data)


def api_lideres(request):
    """API para listar líderes (colaboradores que são líderes de alguém)"""
    lideres = Colaborador.objects.filter(
        liderados__isnull=False
    ).distinct().order_by('nome_completo')
    
    data = {
        'lideres': [
            {
                'id': l.id,
                'nome': l.nome_completo
            }
            for l in lideres
        ]
    }
    
    return JsonResponse(data)


def api_supervisores(request):
    """API para listar supervisores (colaboradores que são supervisores de alguém)"""
    supervisores = Colaborador.objects.filter(
        supervisionados__isnull=False
    ).distinct().order_by('nome_completo')
    
    data = {
        'supervisores': [
            {
                'id': s.id,
                'nome': s.nome_completo
            }
            for s in supervisores
        ]
    }
    
    return JsonResponse(data)


@login_required
def atualizar_liderancas_em_massa(request):
    """View para atualizar líder, supervisor e gerente em massa por setor e turno"""
    from django.shortcuts import render
    from organization.models import Setor
    from core.models import TURNOS_CHOICES
    from django.db.models import Q
    
    setor_id = request.POST.get('setor_id', '')
    turno = request.POST.get('turno', '')
    lider_id = request.POST.get('lider_id', '')
    supervisor_id = request.POST.get('supervisor_id', '')
    gerente_id = request.POST.get('gerente_id', '')
    
    # Obter dados para o formulário
    setores = Setor.objects.filter(ativo=True).order_by('nome')
    turnos = TURNOS_CHOICES
    
    # Listar colaboradores que podem ser líderes, supervisores ou gerentes
    pessoas = Colaborador.objects.filter(is_active=True, afastado=False).order_by('nome_completo')
    
    # Colaboradores que serão atualizados
    colaboradores_afetados = Colaborador.objects.filter(
        is_active=True,
        afastado=False
    )
    
    # Aplicar filtros
    if setor_id:
        try:
            colaboradores_afetados = colaboradores_afetados.filter(setor_id=int(setor_id))
        except:
            pass
    
    if turno:
        colaboradores_afetados = colaboradores_afetados.filter(turno=turno)
    
    # Contar colaboradores que serão atualizados
    total_atualizacoes = colaboradores_afetados.count()
    
    # Se é POST e tem confirmação, atualizar
    if request.method == 'POST' and setor_id and turno:
        confirmar = request.POST.get('confirmar', '')
        
        if confirmar == 'sim':
            updates = {}
            if lider_id:
                try:
                    updates['lider_id'] = int(lider_id)
                except:
                    pass
            if supervisor_id:
                try:
                    updates['supervisor_id'] = int(supervisor_id)
                except:
                    pass
            if gerente_id:
                try:
                    updates['gerente_id'] = int(gerente_id)
                except:
                    pass
            
            if updates:
                updated_count = colaboradores_afetados.update(**updates)
                
                return render(request, 'rh/atualizar_liderancas_em_massa.html', {
                    'setores': setores,
                    'turnos': turnos,
                    'pessoas': pessoas,
                    'sucesso': True,
                    'atualizado_count': updated_count,
                    'setor_nome': Setor.objects.get(id=setor_id).nome if setor_id else '',
                    'turno_label': dict(turnos).get(turno, ''),
                })
    
    # Mostrar preview se há filtros
    preview_colaboradores = []
    if setor_id and turno:
        preview_colaboradores = colaboradores_afetados[:20]  # Mostrar até 20 na preview
    
    context = {
        'setores': setores,
        'turnos': turnos,
        'pessoas': pessoas,
        'setor_id': setor_id,
        'turno': turno,
        'lider_id': lider_id,
        'supervisor_id': supervisor_id,
        'gerente_id': gerente_id,
        'preview_colaboradores': preview_colaboradores,
        'total_atualizacoes': total_atualizacoes,
    }
    
    return render(request, 'rh/atualizar_liderancas_em_massa.html', context)

