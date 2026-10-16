"""Importa a planilha "Acompanhamento - Plano de Teste" (aba Dados) para os planos de homologação.

Uso: python manage.py importar_homologacoes caminho/da/planilha.xlsm [--dry-run]

Cada combinação (Plano de Testes, Tratamento, Máquina) vira um PlanoHomologacao com as 17 etapas.
Tratamentos e máquinas são localizados pelo nome/código; os que não existirem são criados (tratamento)
ou reportados (máquina). É seguro rodar de novo: planos já existentes são atualizados, não duplicados.
"""
import re
from collections import OrderedDict
from datetime import date, datetime

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from laboratorio.models import EtapaHomologacao, PlanoHomologacao, TratamentoAntiReflexo
from maquinas.models import Maquina


def _data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None


class Command(BaseCommand):
    help = "Importa planos de homologação da planilha de acompanhamento (aba Dados)."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--dry-run", action="store_true", help="Só mostra o que seria importado.")

    def handle(self, *args, **opts):
        try:
            wb = openpyxl.load_workbook(opts["arquivo"], data_only=True)
            ws = wb["Dados"]
        except Exception as exc:  # arquivo ausente, formato inválido, aba inexistente
            raise CommandError(f"Não foi possível ler a aba 'Dados': {exc}")

        planos = OrderedDict()
        for row in ws.iter_rows(min_row=10, values_only=True):
            _id, plano_dt, trat, maq, etapa, dt, resultado, obs = (list(row) + [None] * 8)[:8]
            if not (trat and maq and etapa):
                continue
            chave = (_data(plano_dt), str(trat).strip(), str(maq).strip())
            planos.setdefault(chave, []).append((str(etapa).strip(), _data(dt), (resultado or "").strip(), (obs or "").strip()))

        maquinas_ausentes = set()
        criados = atualizados = 0
        with transaction.atomic():
            for (data_plano, trat_nome, maq_cod), etapas in planos.items():
                maquina = Maquina.objects.filter(codigo__iexact=maq_cod).first()
                if not maquina:
                    maquinas_ausentes.add(maq_cod)
                    continue
                tratamento, _ = TratamentoAntiReflexo.objects.get_or_create(nome=trat_nome)
                plano, novo = PlanoHomologacao.objects.get_or_create(
                    tratamento=tratamento, maquina=maquina, data_plano=data_plano or date.today()
                )
                if novo:
                    plano.criar_etapas_padrao()
                    criados += 1
                else:
                    atualizados += 1

                por_ordem = {e.ordem: e for e in plano.etapas.all()}
                observacoes_plano = []
                resultado_plano = ""
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
                    if obs and obs not in observacoes_plano:
                        observacoes_plano.append(obs)
                plano.resultado = resultado_plano if resultado_plano in dict(PlanoHomologacao.RESULTADO_CHOICES) else ""
                plano.observacoes = " | ".join(observacoes_plano)
                plano.save()

            if opts["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Planos criados: {criados} · atualizados: {atualizados}" + (" (dry-run, nada gravado)" if opts["dry_run"] else "")
        ))
        if maquinas_ausentes:
            self.stdout.write(self.style.WARNING(
                "Máquinas não encontradas (cadastre com o código exato e rode de novo): " + ", ".join(sorted(maquinas_ausentes))
            ))
