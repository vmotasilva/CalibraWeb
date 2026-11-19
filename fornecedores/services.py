"""Regras de negócio do módulo de Fornecedores (pontuação e classificação das avaliações)."""
from django.db.models import Count

from .models import AvaliacaoFornecedor, RespostaAvaliacao

# Cada resposta "NÃO" (ocorrência) em um registro de monitoramento desconta esta pontuação.
PENALIDADE_OCORRENCIA = 0.5
PONTUACAO_BASE_MONITORAMENTO = 100.0


def percentual(sim, total):
    return (sim / total * 100) if total else 0.0


def classificar_selecao(pct):
    if pct >= 80:
        return "Excelente"
    if pct >= 60:
        return "Bom"
    if pct >= 40:
        return "Satisfatório"
    return "Insatisfatório"


def classificar_reavaliacao(pct):
    return "Aprovado" if pct >= 60 else "Reprovado"


def classificar_monitoramento(pontuacao):
    if pontuacao >= 75:
        return "Excelente"
    if pontuacao >= 50:
        return "Bom"
    return "Ruim"


def pontuacao_monitoramento(ocorrencias):
    """100 - 0,5 por ocorrência, nunca abaixo de zero."""
    return max(0.0, PONTUACAO_BASE_MONITORAMENTO - ocorrencias * PENALIDADE_OCORRENCIA)


def monitoramentos():
    """Registros de monitoramento (exclui os de matriz de seleção, que também são gravados como MONITORAMENTO)."""
    return AvaliacaoFornecedor.objects.filter(tipo="MONITORAMENTO", respostas_matriz__isnull=True)


def ocorrencias_por_pergunta(fornecedor, ano):
    """{pergunta_id: nº de respostas NÃO} dos monitoramentos do fornecedor no ano."""
    qs = (
        RespostaAvaliacao.objects.filter(
            resposta=False,
            avaliacao__in=monitoramentos().filter(fornecedor=fornecedor, data__year=ano),
        )
        .values("pergunta_id")
        .annotate(total=Count("id"))
    )
    return {row["pergunta_id"]: row["total"] for row in qs}


def pontuacoes_monitoramento_por_fornecedor(ano):
    """{fornecedor_id: pontuação do ano} apenas para quem tem monitoramento no ano."""
    com_registro = set(
        monitoramentos().filter(data__year=ano).values_list("fornecedor_id", flat=True).distinct()
    )
    ocorrencias = {
        row["avaliacao__fornecedor_id"]: row["total"]
        for row in RespostaAvaliacao.objects.filter(
            resposta=False,
            avaliacao__in=monitoramentos().filter(data__year=ano),
        )
        .values("avaliacao__fornecedor_id")
        .annotate(total=Count("id"))
    }
    return {fid: pontuacao_monitoramento(ocorrencias.get(fid, 0)) for fid in com_registro}
