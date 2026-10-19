import io, sys
from datetime import time
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
import openpyxl
from laboratorio.models import RegraTurnoCoating, RendimentoHCRegistro, RendimentoHCItem
from laboratorio import hc_rendimento as hc

ARQ = r"C:/Users/Vinícius Mota/Downloads/Rendimento HC - TEC - 2025.xlsx"

class Real(TestCase):
    def test_real(self):
        for i in (1, 2, 3):
            RegraTurnoCoating.objects.create(nome=f"Turno 0{i}", hora_inicio=time(i), hora_fim=time(i + 1))
        call_command("importar_rendimento_hc", ARQ)
        wb = openpyxl.load_workbook(ARQ, read_only=True, data_only=True)
        ws = wb["Respostas"]
        tot_k = tot_ai = 0
        for r in ws.iter_rows(min_row=2, values_only=True):
            if r[6] is None or r[6].year < 2020: continue
            tot_k += r[10] or 0
            tot_ai += sum((r[i] or 0) for i in range(22, 33) if isinstance(r[i], (int, float)))
        wb.close()
        agg = RendimentoHCRegistro.objects.aggregate(k=Sum("qtd_lentes"), r=Sum("qtd_retrabalho"))
        out = io.open(r"C:/Users/VINCIU~1/AppData/Local/Temp/claude/real.txt", "w", encoding="utf-8")
        out.write(f"sheet K={tot_k} AI(motivos)={tot_ai} | db K={agg['k']} R={agg['r']} n={RendimentoHCRegistro.objects.count()}\n")
        out.write(f"vinculados={RendimentoHCRegistro.objects.filter(colaborador__isnull=False).count()} garra_null={RendimentoHCRegistro.objects.filter(tipo_garra__isnull=True).count()} turno_null={RendimentoHCRegistro.objects.filter(turno__isnull=True).count()}\n")
        out.write(str(hc.propostas_sincronizacao()['sem_vinculo'][:15]) + "\n")
        from datetime import date
        d = hc.retrabalho_ano(2025)
        for l in d['linhas']: out.write(f"{l['mes']} prod={l['produzidas']} ret={l['retrabalho']} r1={l['rend1']} r2={l['rend2']}\n")
        out.close()
