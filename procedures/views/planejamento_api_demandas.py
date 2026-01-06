from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from procedures.models import PerfilTreinamento, Procedimento, RegistroTreinamento
from rh.models import Colaborador


@login_required
def api_demandas_por_perfil_view(request):
    """
    Endpoint JSON para buscar demandas (procedimentos pendentes) por perfil
    Retorna:
    - procedimentos: Lista de procedimentos com demandas nesse perfil
    - colaboradores: Lista de colaboradores que têm esse perfil
    - total_pendentes: Total de demandas pendentes
    
    Parâmetros GET:
    - perfil_id: ID do perfil de treinamento
    """
    perfil_id = request.GET.get('perfil_id', '').strip()
    
    if not perfil_id:
        return JsonResponse({
            'procedimentos': [],
            'colaboradores': [],
            'total_pendentes': 0,
            'error': 'perfil_id é obrigatório'
        })
    
    try:
        perfil = PerfilTreinamento.objects.get(id=perfil_id)
        
        # Buscar colaboradores com este perfil
        colaboradores_com_perfil = Colaborador.objects.filter(
            perfis_treinamento__perfil=perfil,
            is_active=True
        ).distinct().order_by('nome_completo')
        
        # Buscar grupos, subgrupos e seus procedimentos
        grupos = []
        for grupo in perfil.grupos.all().order_by('ordem'):
            subgrupos = []
            for subgrupo in grupo.subgrupos.all().order_by('ordem'):
                # Buscar procedimentos deste subgrupo com demandas
                procedimentos_subgrupo = []
                for proc in subgrupo.procedimentos.all().order_by('codigo'):
                    # Contar demandas pendentes
                    demanda_count = 0
                    for colab in colaboradores_com_perfil:
                        registro = RegistroTreinamento.objects.filter(
                            colaborador=colab,
                            procedimento=proc
                        ).first()
                        
                        if not registro or registro.status_treinamento != 'OK':
                            demanda_count += 1
                    
                    if demanda_count > 0:
                        procedimentos_subgrupo.append({
                            'id': proc.id,
                            'codigo': proc.codigo,
                            'nome': proc.nome,
                            'demanda_count': demanda_count
                        })
                
                subgrupos.append({
                    'id': subgrupo.id,
                    'nome': subgrupo.nome,
                    'procedimentos': procedimentos_subgrupo,
                    'procedimentos_count': len(procedimentos_subgrupo)
                })
            
            grupos.append({
                'id': grupo.id,
                'nome': grupo.nome,
                'subgrupos': subgrupos
            })
        
        # Preparar dados dos colaboradores
        dados_colaboradores = [
            {
                'id': colab.id,
                'nome': colab.nome_completo,
                'matricula': colab.matricula or '-',
                'setor': colab.setor.nome if colab.setor else '-'
            }
            for colab in colaboradores_com_perfil
        ]
        
        # Contar total de procedimentos com demanda
        total_procedimentos = sum(
            len(sub['procedimentos']) 
            for grupo in grupos 
            for sub in grupo['subgrupos']
        )
        
        data = {
            'perfil_nome': perfil.nome,
            'grupos': grupos,
            'colaboradores': dados_colaboradores,
            'total_pendentes': total_procedimentos,
            'total_colaboradores': len(dados_colaboradores)
        }
        
        return JsonResponse(data)
    except PerfilTreinamento.DoesNotExist:
        return JsonResponse({
            'procedimentos': [],
            'colaboradores': [],
            'total_pendentes': 0,
            'error': 'Perfil não encontrado'
        })
