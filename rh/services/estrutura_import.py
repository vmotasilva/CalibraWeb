# -*- coding: utf-8 -*-
"""
Importação da Estrutura de Equipes e Turnos a partir de planilha .xlsx.

Layout esperado (como a planilha de alocação por posto):
  coluna A = Bloco (só na primeira linha do bloco), coluna B = Posto de trabalho,
  e uma coluna por turno ("Turno 01", "Turno 02", "Turno 03") com o titular.
  Valores especiais na célula do turno: VAGO/VAGA, RESERVA, PARADO/PARADA.
  Bloco sem posto na coluna B vira um posto com o mesmo nome do bloco.
  Colunas além do primeiro conjunto de turnos (listas de pessoas, notas) são ignoradas.

Este módulo só lê e interpreta; nada é gravado aqui.
"""
import re
import unicodedata

from openpyxl import load_workbook

from rh.models import Colaborador

TURNO_POR_NUMERO = {"1": "TURNO_1", "2": "TURNO_2", "3": "TURNO_3"}
MAX_LINHAS = 500
MAX_COLUNAS = 15
MAX_CANDIDATOS = 8


class PlanilhaInvalida(Exception):
    pass


def normaliza(texto):
    """Minúsculas, sem acento, espaços colapsados."""
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().casefold()


def _texto(valor):
    if valor is None:
        return None
    t = re.sub(r"\s+", " ", str(valor)).strip()
    return t or None


def interpreta_celula(valor):
    """Retorna (situacao, nome): situacao em VAGO/RESERVA/PARADO, ou ATIVO com o nome da pessoa."""
    n = normaliza(valor)
    if n in ("vago", "vaga"):
        return "VAGO", None
    if n.startswith("reserva"):
        return "RESERVA", None
    if n.startswith("parad"):
        return "PARADO", None
    return "ATIVO", _texto(valor)


def ler_planilha(arquivo):
    """Lê o .xlsx e devolve {'blocos': [...], 'avisos': [...]} sem tocar no banco."""
    try:
        wb = load_workbook(arquivo, read_only=True, data_only=True)
    except Exception as exc:
        raise PlanilhaInvalida("Não foi possível abrir o arquivo. Envie uma planilha .xlsx válida.") from exc
    try:
        ws = wb.worksheets[0]
        linhas = list(ws.iter_rows(max_row=MAX_LINHAS, max_col=MAX_COLUNAS, values_only=True))
    finally:
        wb.close()

    # cabeçalho: primeira linha (nas 10 primeiras) com células "Turno 01/02/03"
    cab_idx, colunas = None, {}
    for i, linha in enumerate(linhas[:10]):
        achados = {}
        for j, v in enumerate(linha):
            m = re.fullmatch(r"turno\s*0?([1-3])", normaliza(v))
            if m and m.group(1) not in achados:  # primeira ocorrência de cada turno (ignora listas à direita)
                achados[m.group(1)] = j
        if achados:
            cab_idx, colunas = i, {TURNO_POR_NUMERO[k]: j for k, j in achados.items()}
            break
    if cab_idx is None:
        raise PlanilhaInvalida('Não encontrei o cabeçalho com as colunas "Turno 01", "Turno 02" ou "Turno 03".')

    primeira_turno = min(colunas.values())
    if primeira_turno < 2:
        raise PlanilhaInvalida("Esperava as colunas de Bloco (A) e Posto (B) antes das colunas de turno.")

    blocos, avisos = [], []
    bloco_atual = None
    for n, linha in enumerate(linhas[cab_idx + 1:], start=cab_idx + 2):
        nome_bloco = _texto(linha[0] if len(linha) > 0 else None)
        nome_posto = _texto(linha[1] if len(linha) > 1 else None)
        celulas = {t: _texto(linha[j] if j < len(linha) else None) for t, j in colunas.items()}
        if not nome_bloco and not nome_posto and not any(celulas.values()):
            continue
        if nome_bloco:
            bloco_atual = {"nome": nome_bloco, "postos": []}
            blocos.append(bloco_atual)
            if not nome_posto:
                nome_posto = nome_bloco  # bloco sem posto: posto com o mesmo nome
        if bloco_atual is None:
            avisos.append(f"Linha {n}: ignorada (não há bloco definido acima).")
            continue
        if not nome_posto:
            avisos.append(f"Linha {n}: ignorada (posto sem nome).")
            continue
        if any(normaliza(p["nome"]) == normaliza(nome_posto) for p in bloco_atual["postos"]):
            avisos.append(f'Linha {n}: posto "{nome_posto}" repetido no bloco "{bloco_atual["nome"]}" — ignorado.')
            continue
        turnos = {}
        for t, v in celulas.items():
            if v:
                situacao, pessoa = interpreta_celula(v)
                turnos[t] = {"original": v, "situacao": situacao, "pessoa": pessoa}
        bloco_atual["postos"].append({"nome": nome_posto, "turnos": turnos, "linha": n})

    blocos = [b for b in blocos if b["postos"]]
    if not blocos:
        raise PlanilhaInvalida("Nenhum bloco/posto encontrado abaixo do cabeçalho.")
    return {"blocos": blocos, "avisos": avisos, "turnos": sorted(colunas)}


# ------------------------------------------------------------------ casamento de pessoas
class IndicePessoas:
    """Índice dos colaboradores ativos para casar nomes curtos (primeiro nome, apelido, nome abreviado)."""

    def __init__(self):
        self.itens = []
        for c in Colaborador.objects.filter(is_active=True).select_related("setor"):
            tokens = normaliza(c.nome_completo).split()
            if tokens:
                self.itens.append((c, tokens, normaliza(c.nome_abreviado)))

    def candidatos(self, nome, setor_id=None, turno=None):
        alvo = normaliza(nome).split()
        if not alvo:
            return []
        texto = " ".join(alvo)
        exatos, parciais = [], []
        for c, tokens, abrev in self.itens:
            if abrev == texto or tokens[: len(alvo)] == alvo:
                exatos.append(c)
            elif tokens[0] == alvo[0] or all(t in tokens for t in alvo):
                parciais.append(c)
        achados = exatos or parciais
        if not achados:  # último recurso: qualquer parte do nome (ex.: apelido = sobrenome)
            achados = [c for c, tokens, _ in self.itens if alvo[0] in tokens]

        def rank(c):
            return (0 if setor_id and c.setor_id == setor_id else 1, 0 if turno and c.turno == turno else 1, c.nome_completo)

        return sorted(achados, key=rank)[:MAX_CANDIDATOS]


def serializa_pessoa(c):
    return {
        "id": c.id,
        "nome": c.nome_completo,
        "matricula": c.matricula,
        "cargo": c.cargo or "",
        "setor": c.setor.nome if c.setor_id else "",
        "turno": c.turno,
    }


def monta_previa(dados, setor_id=None):
    """Acrescenta a cada célula de pessoa os candidatos e a decisão sugerida.

    Decisão: "c:<id>" (pessoa), "s:VAGO" / "s:RESERVA" / "s:PARADO", ou "" (a resolver na revisão).
    """
    indice = IndicePessoas()
    for bloco in dados["blocos"]:
        for posto in bloco["postos"]:
            for turno, cel in posto["turnos"].items():
                if cel["situacao"] != "ATIVO":
                    cel["decisao"], cel["candidatos"], cel["status"] = "s:" + cel["situacao"], [], "ok"
                    continue
                cands = indice.candidatos(cel["pessoa"], setor_id, turno)
                cel["candidatos"] = [serializa_pessoa(c) for c in cands]
                preferidos = [c for c in cands if setor_id and c.setor_id == setor_id]
                if len(cands) == 1:
                    cel["decisao"], cel["status"] = f"c:{cands[0].id}", "ok"
                elif len(preferidos) == 1:
                    cel["decisao"], cel["status"] = f"c:{preferidos[0].id}", "ok"
                elif cands:
                    cel["decisao"], cel["status"] = "", "ambiguo"
                else:
                    cel["decisao"], cel["status"] = "", "nao_encontrado"
    return dados
