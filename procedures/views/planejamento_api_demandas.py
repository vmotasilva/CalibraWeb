from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from collections import defaultdict
from django.db.models import Prefetch
from procedures.models import PerfilTreinamento, Procedimento, RegistroTreinamento, SubGrupoTreinamento
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

        # Buscar colaboradores com este perfil (carrega setor em uma query)
        colaboradores_com_perfil = list(
            Colaborador.objects.filter(
            perfis_treinamento__perfil=perfil,
            is_active=True
            )
            .select_related('setor')
            .distinct()
            .order_by('nome_completo')
        )
        colaborador_ids = [c.id for c in colaboradores_com_perfil]

        # Prefetch completo da estrutura perfil -> grupos -> subgrupos -> procedimentos
        procedimentos_qs = Procedimento.objects.only('id', 'codigo', 'nome').order_by('codigo')
        subgrupos_qs = SubGrupoTreinamento.objects.order_by('ordem', 'nome').prefetch_related(
            Prefetch('procedimentos', queryset=procedimentos_qs)
        )
        grupos_qs = perfil.grupos.all().order_by('ordem', 'nome').prefetch_related(
            Prefetch('subgrupos', queryset=subgrupos_qs)
        )

        grupos_obj = list(grupos_qs)

        # Coleta todos os procedimentos da estrutura para calcular pendências em lote
        procedimento_ids = set()
        for grupo in grupos_obj:
            for subgrupo in grupo.subgrupos.all():
                for proc in subgrupo.procedimentos.all():
                    procedimento_ids.add(proc.id)

        # Mapa procedimento -> colaboradores com status OK (uma única consulta de registros)
        ok_colaboradores_por_procedimento = defaultdict(set)
        if colaborador_ids and procedimento_ids:
            registros = RegistroTreinamento.objects.filter(
                colaborador_id__in=colaborador_ids,
                procedimento_id__in=procedimento_ids,
            ).select_related('procedimento')

            for registro in registros:
                # status_treinamento é propriedade de negócio; calculamos 1 vez por registro.
                if registro.status_treinamento == 'OK':
                    ok_colaboradores_por_procedimento[registro.procedimento_id].add(registro.colaborador_id)

        total_colaboradores = len(colaborador_ids)

        # Buscar grupos, subgrupos e procedimentos com demanda usando os mapas em memória
        grupos = []
        for grupo in grupos_obj:
            subgrupos = []
            for subgrupo in grupo.subgrupos.all():
                procedimentos_subgrupo = []
                for proc in subgrupo.procedimentos.all():
                    ok_count = len(ok_colaboradores_por_procedimento.get(proc.id, set()))
                    demanda_count = max(total_colaboradores - ok_count, 0)

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
