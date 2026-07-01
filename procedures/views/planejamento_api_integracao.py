from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from procedures.models import PerfilTreinamento, PacoteIntegracao, ColaboradorPerfil
from rh.models import Colaborador

@login_required
def api_integracao_por_perfil_view(request):
    """
    API para buscar os procedimentos do pacote de integração e os colaboradores
    associados a um perfil específico.
    """
    perfil_id = request.GET.get('perfil_id')
    
    if not perfil_id:
        return JsonResponse({'error': 'ID do perfil não fornecido'}, status=400)
        
    try:
        perfil = PerfilTreinamento.objects.get(id=perfil_id)
        
        # Obter o pacote de integração (se existir)
        try:
            pacote = PacoteIntegracao.objects.get(perfil=perfil, ativo=True)
            procedimentos = pacote.procedimentos.all()
            procedimentos_data = [
                {
                    'id': proc.id,
                    'codigo': proc.codigo,
                    'nome': proc.titulo or 'Sem título',
                } for proc in procedimentos
            ]
        except PacoteIntegracao.DoesNotExist:
            procedimentos_data = []
            
        # Obter colaboradores ativos que possuem este perfil
        colaboradores_perfis = ColaboradorPerfil.objects.filter(perfil=perfil, ativo=True).select_related('colaborador')
        colaboradores = [cp.colaborador for cp in colaboradores_perfis if cp.colaborador.ativo]
        
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
            'total_procedimentos': len(procedimentos_data),
            'total_colaboradores': len(colaboradores_data),
            'procedimentos': procedimentos_data,
            'colaboradores': colaboradores_data
        })
        
    except PerfilTreinamento.DoesNotExist:
        return JsonResponse({'error': 'Perfil não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
