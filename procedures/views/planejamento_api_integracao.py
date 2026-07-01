from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from procedures.models import PerfilTreinamento, PacoteIntegracao, ColaboradorPerfil
from rh.models import Colaborador

@login_required
def api_integracao_por_perfil_view(request):
    """
    API para buscar os procedimentos dos pacotes de integração e os colaboradores
    associados a um perfil específico.
    """
    perfil_id = request.GET.get('perfil_id')
    
    if not perfil_id:
        return JsonResponse({'error': 'ID do perfil não fornecido'}, status=400)
        
    try:
        perfil = PerfilTreinamento.objects.get(id=perfil_id)
        
        # Obter todos os pacotes de integração ativos para o perfil
        pacotes = PacoteIntegracao.objects.filter(perfil=perfil, ativo=True).prefetch_related('procedimentos')
        
        pacotes_data = []
        procedimentos_consolidados = set()
        procedimentos_list = []
        
        for pacote in pacotes:
            procs_data = []
            for proc in pacote.procedimentos.all():
                proc_info = {
                    'id': proc.id,
                    'codigo': proc.codigo,
                    'nome': proc.nome or 'Sem título',
                    'matriz': proc.matriz or ''
                }
                procs_data.append(proc_info)
                
                # Consolidar em lista única de procedimentos
                if proc.id not in procedimentos_consolidados:
                    procedimentos_consolidados.add(proc.id)
                    procedimentos_list.append(proc_info)
                    
            pacotes_data.append({
                'id': pacote.id,
                'nome': pacote.nome,
                'procedimentos': procs_data
            })
            
        # Obter colaboradores ativos que possuem este perfil
        colaboradores_perfis = ColaboradorPerfil.objects.filter(perfil=perfil, ativo=True).select_related('colaborador')
        colaboradores = [cp.colaborador for cp in colaboradores_perfis if cp.colaborador.is_active]
        
        colaboradores_data = [
            {
                'id': colab.id,
                'nome': colab.nome_completo,
                'matricula': colab.matricula or '-',
                'setor': getattr(colab.setor, 'nome', 'Sem setor') if hasattr(colab, 'setor') else 'Sem setor'
            } for colab in colaboradores
        ]
        
        # Order by nome
        colaboradores_data = sorted(colaboradores_data, key=lambda x: x['nome'])
        
        return JsonResponse({
            'perfil_nome': perfil.nome,
            'total_colaboradores': len(colaboradores_data),
            'pacotes': pacotes_data,
            'procedimentos_consolidados': procedimentos_list,
            'colaboradores': colaboradores_data
        })
        
    except PerfilTreinamento.DoesNotExist:
        return JsonResponse({'error': 'Perfil não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
