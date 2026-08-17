
import re

with open('auditoria/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_view = '''@login_required
def iso_revisao_dashboard(request, auditoria_id):
    from .models import AuditoriaIso, RespostaEntrevistaIso, AgendaAuditoriaIso, ItemNorma, AvaliacaoFinalRequisitoIso
    from collections import defaultdict
    
    auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
    
    respostas = RespostaEntrevistaIso.objects.filter(
        auditoria=auditoria
    ).exclude(
        classificacao='NA'
    ).select_related('pergunta')
    
    agendas = AgendaAuditoriaIso.objects.filter(auditoria=auditoria).prefetch_related('perguntas')
    
    pergunta_agendas_map = defaultdict(list)
    for agenda in agendas:
        for p in agenda.perguntas.all():
            pergunta_agendas_map[p.id].append(agenda)
            
    avaliacoes_finais = {
        av.item_norma_id: av.classificacao
        for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)
    }
                
    # Agrupamento por ItemNorma
    itens_map = {}
    
    for resp in respostas:
        resp.agendas_avaliadas = pergunta_agendas_map.get(resp.pergunta.id, [])
        
        # Uma resposta pode pertencer a vários itens da norma
        for item in resp.pergunta.itens_norma.all():
            if item.id not in itens_map:
                itens_map[item.id] = {
                    'item': item,
                    'respostas': [],
                    'pior_status': 'C'
                }
            itens_map[item.id]['respostas'].append(resp)
            
            # Atualiza o pior status do campo (bruto) (P > NC > OM > C)
            status_atual = itens_map[item.id]['pior_status']
            novo_status = resp.classificacao
            
            peso = {'P': 4, 'NC': 3, 'OM': 2, 'C': 1}
            if peso.get(novo_status, 0) > peso.get(status_atual, 0):
                itens_map[item.id]['pior_status'] = novo_status

    # Sobrescreve com avaliação final, se existir
    for item_id, data in itens_map.items():
        if item_id in avaliacoes_finais:
            data['pior_status'] = avaliacoes_finais[item_id]
                
    # Converte dicionário em lista ordenada
    blocos = []
    for item_id, data in sorted(itens_map.items(), key=lambda x: x[1]['item'].referencia):
        blocos.append(data)
        
    context = {
        'auditoria': auditoria,
        'blocos': blocos,
    }
    
    return render(request, 'auditoria/iso/revisao_dashboard.html', context)

@login_required
@require_POST
def api_iso_revisao_reverter(request):
    import json
    from django.http import JsonResponse
    from .models import ItemNorma, AvaliacaoFinalRequisitoIso, AuditoriaIso, ComentarioRespostaAuditoria
    
    try:
        data = json.loads(request.body)
        item_norma_id = data.get('item_norma_id')
        auditoria_id = data.get('auditoria_id')
        novo_status = data.get('novo_status')
        argumentacao = data.get('argumentacao')
        
        item_norma = get_object_or_404(ItemNorma, pk=item_norma_id)
        auditoria = get_object_or_404(AuditoriaIso, pk=auditoria_id)
        
        avaliacao, created = AvaliacaoFinalRequisitoIso.objects.update_or_create(
            auditoria=auditoria,
            item_norma=item_norma,
            defaults={
                'classificacao': novo_status,
                'justificativa': argumentacao,
                'atualizado_por': request.user
            }
        )
        
        texto_log = f"[VEREDICTO FINAL] Requisito {item_norma.referencia} definido como {novo_status}. Argumentação: {argumentacao}"
            
        ComentarioRespostaAuditoria.objects.create(
            autor=request.user,
            texto=texto_log,
            data_referencia=auditoria.data_inicio
        )
            
        return JsonResponse({'success': True, 'message': 'Status final atualizado com sucesso.', 'novo_status': novo_status})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
'''

pattern = re.compile(r'@login_required\ndef iso_revisao_dashboard.*', re.DOTALL)
new_content = pattern.sub(new_view, content)

with open('auditoria/views.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
