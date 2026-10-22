"""Equipe HMC unificada: Preparação e Montagem (Coating), Inspeção do Controle Final e Colaborador do HC numa só lista.

Cada coluna continua sendo gravada no cadastro que o respectivo módulo já usa:
- Preparação / Montagem  -> EquipeCoating (pode_preparar / pode_montar; a Montagem também alimenta o campo de montagem do CF)
- CF inspeção            -> EquipeCF (ativo)
- HC                     -> EquipeHC (ativo)
"""
from laboratorio.models import EquipeCF, EquipeCoating, EquipeHC


def matriz():
    """Uma linha por colaborador, com o que ele pode operar em cada módulo."""
    coating = {e.colaborador_id: e for e in EquipeCoating.objects.select_related("colaborador")}
    cf = {e.colaborador_id: e for e in EquipeCF.objects.select_related("colaborador")}
    hc = {e.colaborador_id: e for e in EquipeHC.objects.select_related("colaborador")}
    linhas = []
    for pk in set(coating) | set(cf) | set(hc):
        colab = (coating.get(pk) or cf.get(pk) or hc.get(pk)).colaborador
        apelidos = (cf[pk].apelidos if pk in cf and cf[pk].apelidos else (hc[pk].apelidos if pk in hc else ""))
        linhas.append({
            "colaborador": colab,
            "preparar": bool(pk in coating and coating[pk].pode_preparar),
            "montar": bool(pk in coating and coating[pk].pode_montar),
            "cf": bool(pk in cf and cf[pk].ativo),
            "hc": bool(pk in hc and hc[pk].ativo),
            "apelidos": apelidos or "",
        })
    return sorted(linhas, key=lambda x: x["colaborador"].nome_completo)


def salvar(colab, preparar, montar, cf, hc, apelidos=None):
    """Grava todas as colunas de uma vez. Não cria cadastro para a coluna desmarcada de quem nunca esteve nela."""
    if preparar or montar or EquipeCoating.objects.filter(colaborador=colab).exists():
        eq, _ = EquipeCoating.objects.get_or_create(colaborador=colab)
        eq.pode_preparar, eq.pode_montar = bool(preparar), bool(montar)
        eq.save()
    for modelo, marcado in ((EquipeCF, cf), (EquipeHC, hc)):
        if marcado or modelo.objects.filter(colaborador=colab).exists():
            eq, _ = modelo.objects.get_or_create(colaborador=colab)
            eq.ativo = bool(marcado)
            if apelidos is not None:
                eq.apelidos = apelidos[:255]
            eq.save()


def remover(colab):
    """Tira o colaborador de todas as listas (Coating, Controle Final e HC)."""
    EquipeCoating.objects.filter(colaborador=colab).delete()
    EquipeCF.objects.filter(colaborador=colab).delete()
    EquipeHC.objects.filter(colaborador=colab).delete()
