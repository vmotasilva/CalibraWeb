"""Importação da planilha "Acompanhamento - Plano de Teste" (aba Dados) para os planos de homologação.

Cada combinação (Plano de Testes, Tratamento, Máquina) vira um PlanoHomologacao com as 17 etapas já
preenchidas com as datas da planilha, de modo que o status (Aprovado / Em Andamento) e a etapa atual
sejam reconhecidos automaticamente. Planos que já existem no sistema não são alterados, para não
sobrescrever lançamentos feitos depois da importação.
"""
import re
import unicodedata
from collections import OrderedDict
from datetime import date, datetime

import openpyxl
from django.db import transaction

from maquinas.models import Maquina

from .models import PlanoHomologacao, TratamentoAntiReflexo

PRIMEIRA_LINHA_DADOS = 10  # cabeçalho na linha 9 da aba Dados


class PlanilhaInvalida(Exception):
    pass


def _data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper()
    texto = re.sub(r"^C\.\s*", "CRIZAL ", texto)  # "C. ROCK" -> "CRIZAL ROCK"
    return re.sub(r"[^A-Z0-9]", "", texto)


def _localizar_tratamento(nome, tratamentos):
    """Procura o tratamento já cadastrado que corresponde ao nome da planilha (None se não houver)."""
    alvo = _normalizar(nome)
    for chave, t in tratamentos:
        if chave == alvo:
            return t
    # Nome da planilha com complemento (ex.: "BLUE CUT NIKKON" x "BLUE CUT"): aceita se for único
    parecidos = [t for chave, t in tratamentos if chave and (alvo.startswith(chave) or chave.startswith(alvo))]
    return parecidos[0] if len(parecidos) == 1 else None


def _ler_planos(arquivo):
    try:
        wb = openpyxl.load_workbook(arquivo, data_only=True, read_only=True)
        ws = wb["Dados"]
    except Exception as exc:
        raise PlanilhaInvalida(f"Não foi possível ler a aba 'Dados' da planilha ({exc}).")

    planos = OrderedDict()
    try:
        for row in ws.iter_rows(min_row=PRIMEIRA_LINHA_DADOS, values_only=True):
            _id, plano_dt, trat, maq, etapa, dt, resultado, obs = (list(row) + [None] * 8)[:8]
            if not (trat and maq and etapa):
                continue
            chave = (_data(plano_dt), str(trat).strip(), str(maq).strip())
            planos.setdefault(chave, []).append(
                (str(etapa).strip(), _data(dt), str(resultado or "").strip(), str(obs or "").strip())
            )
    finally:
        wb.close()
    if not planos:
        raise PlanilhaInvalida("A aba 'Dados' não tem linhas de plano de testes (esperado a partir da linha 10).")
    return planos


def importar_planilha(arquivo, dry_run=False):
    """Importa os planos da planilha. Retorna um dicionário com o resumo do que foi feito."""
    planos = _ler_planos(arquivo)
    relatorio = {
        "criados": 0,
        "ja_existentes": 0,
        "tratamentos_criados": [],
        "maquinas_criadas": [],
        "aprovados": 0,
        "reprovados": 0,
        "em_andamento": 0,
    }

    with transaction.atomic():
        tratamentos = [(_normalizar(t.nome), t) for t in TratamentoAntiReflexo.objects.all()]
        maquinas = {_normalizar(m.codigo): m for m in Maquina.objects.all()}

        for (data_plano, trat_nome, maq_cod), etapas in planos.items():
            tratamento = _localizar_tratamento(trat_nome, tratamentos)
            if not tratamento:
                tratamento = TratamentoAntiReflexo.objects.create(nome=trat_nome)
                tratamentos.append((_normalizar(tratamento.nome), tratamento))
                relatorio["tratamentos_criados"].append(trat_nome)

            maquina = maquinas.get(_normalizar(maq_cod))
            if not maquina:
                maquina = Maquina.objects.create(codigo=maq_cod)
                maquinas[_normalizar(maq_cod)] = maquina
                relatorio["maquinas_criadas"].append(maq_cod)

            plano, novo = PlanoHomologacao.objects.get_or_create(
                tratamento=tratamento, maquina=maquina, data_plano=data_plano or date.today()
            )
            if not novo:
                relatorio["ja_existentes"] += 1
                continue

            plano.criar_etapas_padrao()
            relatorio["criados"] += 1
            por_ordem = {e.ordem: e for e in plano.etapas.all()}
            observacoes, resultado_plano = [], ""
            for nome, dt, resultado, obs in etapas:
                m = re.match(r"\s*(\d+)\s*-", nome)
                etapa = por_ordem.get(int(m.group(1))) if m else None
                if not etapa:
                    continue
                etapa.data = dt
                etapa.observacoes = obs
                etapa.save(update_fields=["data", "observacoes"])
                if resultado:
                    resultado_plano = resultado.upper()
                if obs and obs not in observacoes:
                    observacoes.append(obs)

            plano.resultado = resultado_plano if resultado_plano in dict(PlanoHomologacao.RESULTADO_CHOICES) else ""
            plano.observacoes = " | ".join(observacoes)
            plano.save()

            status = PlanoHomologacao.objects.prefetch_related("etapas").get(pk=plano.pk).status
            chave = {
                PlanoHomologacao.RESULTADO_APROVADO: "aprovados",
                PlanoHomologacao.RESULTADO_REPROVADO: "reprovados",
            }.get(status, "em_andamento")
            relatorio[chave] += 1

        if dry_run:
            transaction.set_rollback(True)

    return relatorio


def resumo_texto(rel):
    partes = [
        f"{rel['criados']} plano(s) importado(s)",
        f"{rel['aprovados']} aprovado(s)",
        f"{rel['em_andamento']} em andamento",
    ]
    if rel["reprovados"]:
        partes.append(f"{rel['reprovados']} reprovado(s)")
    if rel["ja_existentes"]:
        partes.append(f"{rel['ja_existentes']} já existiam (mantidos como estão)")
    if rel["tratamentos_criados"]:
        partes.append("tratamentos novos: " + ", ".join(rel["tratamentos_criados"]))
    if rel["maquinas_criadas"]:
        partes.append("máquinas novas: " + ", ".join(rel["maquinas_criadas"]))
    return " · ".join(partes)
