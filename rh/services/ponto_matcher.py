import difflib
from rh.models import Colaborador

def sugerir_colaboradores_similares(nome_planilha: str, limit: int = 3, cutoff: float = 0.35):
    """
    Compara o nome vindo na planilha com todos os colaboradores ativos do banco
    e retorna os melhores palpites ordenados por pontuação de similaridade.
    """
    if not nome_planilha:
        return []

    nome_planilha_clean = nome_planilha.strip().upper()
    colaboradores = Colaborador.objects.filter(is_active=True).values('id', 'matricula', 'nome_completo')
    
    sugestoes = []
    for c in colaboradores:
        nome_banco = c['nome_completo'].upper()
        
        # Comparação direta
        ratio_direto = difflib.SequenceMatcher(None, nome_planilha_clean, nome_banco).ratio()
        
        # Inversão para lidar com formatos 'Sobrenome/Prim.Nome' (ex: SILVA/JOAO -> JOAO SILVA)
        partes_planilha = nome_planilha_clean.replace('/', ' ').split()
        nome_reordenado = " ".join(reversed(partes_planilha))
        ratio_inverso = difflib.SequenceMatcher(None, nome_reordenado, nome_banco).ratio()
        
        # Maior pontuação entre direta e invertida
        best_score = max(ratio_direto, ratio_inverso)
        
        if best_score >= cutoff:
            sugestoes.append({
                'id': c['id'],
                'matricula': c['matricula'],
                'nome_completo': c['nome_completo'],
                'score': round(best_score * 100, 1) # Percentual
            })

    sugestoes.sort(key=lambda x: x['score'], reverse=True)
    return sugestoes[:limit]
