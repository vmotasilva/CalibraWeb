"""Utilitários para matching de nomes entre entrada livre e base de dados."""
import difflib
from typing import Optional, Tuple
from rh.models import Colaborador


def calcular_similaridade(nome1: str, nome2: str) -> float:
    """
    Calcula similaridade entre dois nomes usando SequenceMatcher.
    
    Args:
        nome1: Primeiro nome
        nome2: Segundo nome
    
    Returns:
        Percentual de similaridade (0.0 a 1.0)
    """
    if not nome1 or not nome2:
        return 0.0
    
    # Normalizar: minúsculas, remover espaços extras
    n1 = ' '.join(nome1.lower().strip().split())
    n2 = ' '.join(nome2.lower().strip().split())
    
    if n1 == n2:
        return 1.0
    
    return difflib.SequenceMatcher(None, n1, n2).ratio()


def buscar_colaborador_por_nome(
    nome_texto: str,
    threshold: float = 0.85
) -> Tuple[Optional[Colaborador], float]:
    """
    Busca colaborador na base de dados baseado em similaridade de nome.
    
    Args:
        nome_texto: Nome a buscar (entrada livre do usuário)
        threshold: Limite de similaridade (0.0 a 1.0). Padrão: 0.85 (85%)
    
    Returns:
        Tupla (colaborador encontrado ou None, score de similaridade)
    """
    if not nome_texto or not nome_texto.strip():
        return None, 0.0
    
    colaboradores = Colaborador.objects.all()
    melhor_match = None
    melhor_score = 0.0
    
    for colab in colaboradores:
        # Comparar contra nome_completo
        score = calcular_similaridade(nome_texto, colab.nome_completo)
        
        if score > melhor_score:
            melhor_score = score
            melhor_match = colab
    
    # Retornar apenas se passar do threshold
    if melhor_score >= threshold:
        return melhor_match, melhor_score
    
    return None, melhor_score


def tentar_linkar_colaborador(
    nome_texto: str,
    colaborador_fk: Optional[Colaborador] = None,
    threshold: float = 0.85
) -> Optional[Colaborador]:
    """
    Tenta linkar um colaborador usando FK fornecido OU buscando por nome.
    
    Args:
        nome_texto: Nome livre do usuário
        colaborador_fk: FK do colaborador (se selecionado no form)
        threshold: Limite de similaridade para auto-matching
    
    Returns:
        Colaborador para ser salvo, ou None se nenhum match
    """
    # Se já tem FK selecionado, usar direto
    if colaborador_fk:
        return colaborador_fk
    
    # Tentar buscar por nome com similaridade
    colab, score = buscar_colaborador_por_nome(nome_texto, threshold)
    return colab if score >= threshold else None
