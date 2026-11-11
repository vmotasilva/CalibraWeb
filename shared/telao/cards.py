"""Catálogo de cards do Modo Apresentação: id estável, módulo, seção, forma de desenho e tamanhos.

O id de um card é "<módulo>.<card>" (ex.: "kpi.graficos", "lab.motivo"), o mesmo `id` de `providers.PROVEDOR_CARDS`.
Os rótulos e a regra que decide a que card pertence cada slide continuam em `PROVEDOR_CARDS`; aqui ficam só os
metadados que o construtor (automático e manual) precisa para oferecer, posicionar e dimensionar cada card.

Tamanhos em células de uma grade de COLUNAS x LINHAS (o slide é 16:9). Na posição livre os mesmos números viram
percentuais do slide (x/COLUNAS, y/LINHAS).
"""
from . import providers

COLUNAS = 12
LINHAS = 8

SECOES = [
    ("resumo", "Resumo"),
    ("graficos", "Gráficos"),
    ("listas", "Listas"),
    ("ocorrencias", "Ocorrências"),
]

# forma de desenho -> (tamanho mínimo, tamanho padrão) em células (largura, altura)
TAMANHOS = {
    "tiles": ((3, 2), (12, 2)),
    "bars": ((4, 2), (6, 4)),
    "chart": ((4, 3), (8, 5)),
    "cards": ((4, 3), (6, 5)),
}

# id do card -> (seção, forma, parâmetro de instância ou None).
# O parâmetro de instância identifica qual é o card quando o mesmo existe várias vezes (um por indicador, por relatório...).
CARDS = {
    "ocorrencias.totais": ("resumo", "tiles", None),
    "ocorrencias.por_responsavel": ("graficos", "bars", None),
    "ocorrencias.por_modulo": ("graficos", "bars", None),
    "ocorrencias.lista": ("listas", "cards", "grupo"),

    "kpi.ocorrencias": ("ocorrencias", "cards", "indicador"),
    "kpi.situacao": ("resumo", "tiles", None),
    "kpi.graficos": ("graficos", "chart", "indicador"),
    "kpi.motivos": ("listas", "bars", "indicador"),

    "auditoria.ocorrencias": ("ocorrencias", "cards", None),
    "auditoria.conformidade": ("graficos", "bars", None),
    "auditoria.evolucao": ("graficos", "chart", "relatorio"),
    "auditoria.pontos": ("listas", "cards", "relatorio"),

    "metrologia.ocorrencias": ("ocorrencias", "cards", None),
    "metrologia.totais": ("resumo", "tiles", None),
    "metrologia.criticos": ("listas", "cards", None),

    "pcp.ocorrencias": ("ocorrencias", "cards", None),
    "pcp.resumo": ("resumo", "tiles", None),
    "pcp.evolucao": ("graficos", "chart", None),
    "pcp.frequencias": ("graficos", "bars", None),
    "pcp.paginas": ("graficos", "bars", None),

    "laboratorio.ocorrencias": ("ocorrencias", "cards", None),
    "laboratorio.resumo": ("resumo", "tiles", None),
    "laboratorio.dia": ("graficos", "chart", None),
    "laboratorio.mes": ("graficos", "chart", None),
    "laboratorio.turno": ("graficos", "bars", None),
    "laboratorio.motivo": ("graficos", "bars", None),
    "laboratorio.material": ("graficos", "bars", None),
    "laboratorio.colaborador": ("graficos", "bars", None),

    "treinamentos.resumo": ("resumo", "tiles", None),
    "treinamentos.setor_turno": ("graficos", "bars", None),
    "treinamentos.lider": ("graficos", "bars", None),
    "treinamentos.mensal": ("graficos", "chart", None),
    "treinamentos.planejamento": ("resumo", "tiles", None),
    "treinamentos.proximos": ("listas", "cards", None),
}


def card_id(provedor: str, card: str) -> str:
    return f"{provedor}.{card}"


def catalogo() -> list[dict]:
    """Módulo -> seção -> card, na ordem do menu. Só metadados (sem dados nem permissões): quem monta
    a apresentação escolhe daqui, e o módulo só mostra o que o usuário que assiste pode ver."""
    modulos = []
    for modulo, (rotulo, icone) in providers.ROTULOS_PROVEDORES.items():
        por_secao = {k: [] for k, _ in SECOES}
        for cid, rot, *_ in providers.PROVEDOR_CARDS.get(modulo, []):
            secao, forma, instancia = CARDS[card_id(modulo, cid)]
            minimo, padrao = TAMANHOS[forma]
            por_secao[secao].append({
                "id": card_id(modulo, cid), "rotulo": rot, "forma": forma, "instancia": instancia,
                "tam_min": minimo, "tam_padrao": padrao,
            })
        secoes = [{"id": k, "rotulo": r, "cards": por_secao[k]} for k, r in SECOES if por_secao[k]]
        modulos.append({"id": modulo, "rotulo": rotulo, "icone": icone, "secoes": secoes})
    return modulos


def card_do_slide(slide: dict) -> dict | None:
    """Metadados do card a que o slide pertence (None se não for de nenhum card, ex.: slide 'vazio')."""
    cid = slide.get("card_id")
    if not cid or cid not in CARDS:
        return None
    secao, forma, instancia = CARDS[cid]
    return {"id": cid, "secao": secao, "forma": forma, "instancia": instancia}
