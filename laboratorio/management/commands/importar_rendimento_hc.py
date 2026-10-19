"""Importa a aba "Respostas" da planilha de Rendimento HC para os lançamentos do sistema.

Uso: python manage.py importar_rendimento_hc "Rendimento HC - TEC - 2025.xlsx" [--dry-run]

Idempotente: cada linha é identificada pela coluna "Id" do Forms; reexecutar não duplica.
"""
import re
from datetime import date, datetime

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from laboratorio import hc_rendimento as hc
from laboratorio.models import (
    HCCadastro,
    RegraTurnoCoating,
    RendimentoHCItem,
    RendimentoHCRegistro,
)

# Cabeçalhos da planilha -> material / motivo cadastrado (match por início do nome normalizado)
COL_MATERIAIS = [  # (prefixo do cabeçalho de produção, prefixo do de retrabalho, nome do cadastro)
    ("QUANTIDADE DE ORMA", "QUANTIDADE RETRABALHO DE ORMA", "Orma / Orgânico / CR39"),
    ("QUANTIDADE DE POLY BLUE UV", "QUANTIDADE RETRABALHO POLY BLUE UV", "Poly Blue UV"),
    ("QUANTIDADE DE POLY", "QUANTIDADE RETRABALHO DE POLY", "Airwear / TFL / Poly"),
    ("QUANTIDADE DE STYLIS", "QUANTIDADE RETRABALHO DE STYLIS", "Stylis 1.67 / Stylis 1.74"),
    ("QUANTIDADE DE OUTROS FABRICANTES", "QUANTIDADE RETRABALHO DE OUTROS FABRICANTES", "Lista Negra / Terceiros (Outros Fabricantes)"),
]
COL_MOTIVOS = [  # (cabeçalho normalizado sem o prefixo "RETRABALHO ", nome do cadastro)
    ("PONTO DE VERNIZ", "Ponto de Verniz"),
    ("ESCORRIDO DE VERNIZ", "Escorrido de Verniz"),
    ("RISCO", "Risco"),
    ("MAL DESTRATADA", "Mal Destratada"),
    ("MANCHA/EMBACAMENTO", "Mancha/Embaçamento"),
    ("QUEDA NA MAQUINA", "Queda na Máquina"),
    ("SUJEIRA NAO IDENTIFICADA", "Sujeira não Identificada"),
    ("EMPENADA", "Empenada"),
    ("TRINCA/ESTRIAS DE VERNIZ", "Trinca/Estrias de Verniz"),
    ("PONTO POLY BLUE / BLUE CUT", "Ponto Poly Blue / Blue Cut"),
    ("OUTROS", "Outros"),
]
ANO_MIN = 2020


def _int(v):
    try:
        return max(int(float(v)), 0)
    except (TypeError, ValueError):
        return 0


def _para_data(v):
    if isinstance(v, datetime):
        return v.date()
    return v if isinstance(v, date) else None


class Command(BaseCommand):
    help = "Importa a aba 'Respostas' da planilha de Rendimento HC."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--dry-run", action="store_true", help="Só valida e mostra o resumo; não grava.")

    def handle(self, *args, arquivo, dry_run=False, **opts):
        try:
            wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Não foi possível abrir a planilha: {exc}")
        if "Respostas" not in wb.sheetnames:
            raise CommandError("A planilha não tem a aba 'Respostas'.")
        hc.garantir_padroes()
        try:
            self._importar(wb, dry_run)
        finally:
            wb.close()

    def _importar(self, wb, dry_run):
        linhas = wb["Respostas"].iter_rows(values_only=True)
        cab = [hc.norm(str(c or "")) for c in next(linhas)]
        idx = {}
        for i, nome in enumerate(cab):
            idx.setdefault(nome, i)

        def col(nome):
            return idx.get(hc.norm(nome))

        def cabecalho_que_comeca(prefixo):
            return next((i for i, n in enumerate(cab) if n == hc.norm(prefixo)), None)

        cad = {(c.tipo, c.nome): c for c in HCCadastro.objects.all()}
        garras = {hc.norm(c.nome): c for c in HCCadastro.objects.filter(tipo=HCCadastro.TIPO_GARRA)}
        mats = [(cabecalho_que_comeca(p), cabecalho_que_comeca(r), cad[(HCCadastro.TIPO_MATERIAL, n)]) for p, r, n in COL_MATERIAIS]
        motivos = []
        for chave, nome in COL_MOTIVOS:
            i = next((i for i, n in enumerate(cab) if n.replace("\xa0", " ").replace(" ", "") == hc.norm("RETRABALHO " + chave).replace(" ", "")), None)
            motivos.append((i, cad[(HCCadastro.TIPO_MOTIVO, nome)]))
        turnos = {}
        for t in RegraTurnoCoating.objects.all():
            m = re.search(r"\d", t.nome)
            if m:
                turnos.setdefault(int(m.group()), t)
        candidatos = hc.candidatos_colaborador()
        cache_colab = {}

        existentes = set(RendimentoHCRegistro.objects.exclude(id_externo=None).values_list("id_externo", flat=True))
        novos, itens_pend, ignoradas, duplicadas, sem_turno = [], [], 0, 0, 0
        hoje = date.today()
        c_id, c_data, c_turno, c_colab, c_garra = col("Id"), col("Data"), col("Turno"), col("Colaborador"), col("Tipo de Garra")
        c_qtd, c_num = col("Quantidade de Lentes"), col("Numero da Garra")
        for row in linhas:
            if row is None or all(v is None for v in row):
                continue
            id_ext = _int(row[c_id]) if c_id is not None else None
            dia = _para_data(row[c_data])
            if not dia or dia.year < ANO_MIN or dia > date(hoje.year + 1, 12, 31):
                ignoradas += 1
                continue
            if id_ext and id_ext in existentes:
                duplicadas += 1
                continue
            if id_ext:
                existentes.add(id_ext)
            turno_txt = str(row[c_turno] or "")
            m = re.search(r"\d", turno_txt)
            turno = turnos.get(int(m.group())) if m else None
            if m and not turno:
                sem_turno += 1
            nome = str(row[c_colab] or "").strip()
            if nome not in cache_colab:
                cache_colab[nome] = hc.resolver_colaborador(nome, candidatos)
            colab = cache_colab[nome]
            retrab = {cad_: _int(row[i]) for i, cad_ in motivos if i is not None}
            total_ret = sum(retrab.values())
            reg = RendimentoHCRegistro(
                data=dia, turno=turno, turno_nome=turno.nome if turno else (f"{m.group()}º Turno" if m else ""),
                colaborador=colab, colaborador_nome=colab.nome_completo if colab else nome,
                numero_garra=str(row[c_num] or "").strip()[:10] if c_num is not None else "",
                tipo_garra=garras.get(hc.norm(str(row[c_garra] or ""))), qtd_lentes=_int(row[c_qtd]),
                teve_retrabalho=total_ret > 0, qtd_retrabalho=total_ret,
                origem=RendimentoHCRegistro.ORIGEM_IMPORT, id_externo=id_ext or None,
            )
            novos.append(reg)
            pend = []
            for ip, ir, mat in mats:
                if ip is not None and _int(row[ip]):
                    pend.append((RendimentoHCItem.PROD_MATERIAL, mat, _int(row[ip])))
                if ir is not None and _int(row[ir]):
                    pend.append((RendimentoHCItem.RET_MATERIAL, mat, _int(row[ir])))
            pend += [(RendimentoHCItem.RET_MOTIVO, c_, q) for c_, q in retrab.items() if q]
            por_material = sum(q for t, _c, q in pend if t == RendimentoHCItem.RET_MATERIAL)
            if not total_ret and por_material:  # sem motivo informado: usa o retrabalho por material
                reg.qtd_retrabalho, reg.teve_retrabalho = por_material, True
            itens_pend.append(pend)

        vinculados = sum(1 for r in novos if r.colaborador_id)
        self.stdout.write(
            f"Linhas válidas: {len(novos)} | já importadas: {duplicadas} | ignoradas (data inválida): {ignoradas} | "
            f"turno sem regra cadastrada: {sem_turno} | com colaborador vinculado ao RH: {vinculados}"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: nada foi gravado."))
            return

        with transaction.atomic():
            criados = 0
            for ini in range(0, len(novos), 500):
                lote = novos[ini: ini + 500]
                # Salva sem depender de pk retornado pelo bulk_create (compatível com qualquer banco).
                RendimentoHCRegistro.objects.bulk_create(lote)
                ids = {r.id_externo: r.pk for r in RendimentoHCRegistro.objects.filter(id_externo__in=[r.id_externo for r in lote if r.id_externo])}
                itens = []
                for reg, pend in zip(lote, itens_pend[ini: ini + 500]):
                    pk = reg.pk or ids.get(reg.id_externo)
                    itens += [RendimentoHCItem(registro_id=pk, tipo=t, cadastro=c_, quantidade=q) for t, c_, q in pend if pk]
                RendimentoHCItem.objects.bulk_create(itens)
                criados += len(lote)
        self.stdout.write(self.style.SUCCESS(f"Importados {criados} lançamentos."))
