"""Relatórios comparativos (Excel e Word) entre duas execuções da Auditoria Livre."""
import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .evolucao_livre import CLASSES, ORDEM_CATEGORIAS, ROTULO_CLASSE
from .relatorio_livre_docx import (
    _celula, _larguras, _titulo_secao, _tabela_chave_valor, set_cell_background, set_table_borders,
)

COR_CATEGORIA = {  # preenchimento (Excel) e fundo (Word) por categoria de evolução
    "RESOLVIDO": "D1FAE5", "MELHOROU": "CFFAFE", "MANTIDO": "E5E7EB", "PERSISTE": "FEF3C7", "PIOROU": "FEE2E2",
    "NOVO": "DBEAFE", "PENDENTE": "F3F4F6", "AVALIADO": "CFFAFE", "REMOVIDO": "D1D5DB", "NAO_REAVALIADO": "F3F4F6",
}
ROTULOS_CLASSE = {**{c: ROTULO_CLASSE[c] for c in CLASSES}}


def _txt_classe(linha):
    if linha is None:
        return "—"
    t = ROTULO_CLASSE[linha.conclusao]
    if linha.conclusao == "NC" and linha.grau_nc:
        t += f" ({linha.get_grau_nc_display()})"
    return t


def _titulo_execucao(aud):
    return f"Execução {aud.execucao} ({aud.data_inicio:%d/%m/%Y})"


def _fmt_indice(v):
    return "—" if v is None else f"{v:.1f}%".replace(".", ",")


def _fmt_delta(v, pontos=False):
    if v is None:
        return "—"
    sinal = "+" if v > 0 else ""
    if pontos:
        return f"{sinal}{v:.1f}".replace(".", ",") + " p.p."
    return f"{sinal}{v}"


def frase_resumo(comp):
    """Uma frase com o saldo da evolução, para o topo da tela e dos relatórios."""
    c = comp["contagem"]
    partes = []
    for cod, singular, plural in (
        ("RESOLVIDO", "resolvido", "resolvidos"), ("MELHOROU", "melhorou", "melhoraram"),
        ("PERSISTE", "persiste", "persistem"), ("PIOROU", "piorou", "pioraram"),
        ("NOVO", "novo", "novos"), ("PENDENTE", "ainda pendente", "ainda pendentes"),
    ):
        if c[cod]:
            partes.append(f"{c[cod]} {singular if c[cod] == 1 else plural}")
    return ", ".join(partes).capitalize() + "." if partes else "Sem itens para comparar."


# ===================================================================== Excel

def gerar_excel(comp):
    atual, base = comp["atual"], comp["base"]
    wb = Workbook()
    negrito = Font(bold=True)
    cab_fill = PatternFill("solid", fgColor="1F2937")

    def cabecalho(ws, linha, titulos):
        for col, t in enumerate(titulos, start=1):
            c = ws.cell(row=linha, column=col, value=t)
            c.font, c.fill = Font(bold=True, color="FFFFFF"), cab_fill
            c.alignment = Alignment(wrap_text=True, vertical="center")

    ws = wb.active
    ws.title = "Resumo"
    ws.cell(row=1, column=1, value=atual.titulo).font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=f"{_titulo_execucao(base)}  →  {_titulo_execucao(atual)}")
    ws.cell(row=3, column=1, value=frase_resumo(comp))
    cabecalho(ws, 5, ["Classificação", _titulo_execucao(base), _titulo_execucao(atual), "Variação"])
    linha = 6
    for cod in (*CLASSES, "total"):
        ws.cell(row=linha, column=1, value=ROTULO_CLASSE.get(cod, "Total de itens"))
        ws.cell(row=linha, column=2, value=comp["res_base"][cod])
        ws.cell(row=linha, column=3, value=comp["res_atual"][cod])
        ws.cell(row=linha, column=4, value=_fmt_delta(comp["deltas"][cod]))
        linha += 1
    ws.cell(row=linha, column=1, value="Índice de conformidade").font = negrito
    ws.cell(row=linha, column=2, value=_fmt_indice(comp["res_base"]["indice"]))
    ws.cell(row=linha, column=3, value=_fmt_indice(comp["res_atual"]["indice"]))
    ws.cell(row=linha, column=4, value=_fmt_delta(comp["deltas"]["indice"], pontos=True))
    linha += 2
    cabecalho(ws, linha, ["Evolução dos itens", "Quantidade"])
    for cod, rotulo, _cor, n in comp["categorias"]:
        if n:
            linha += 1
            ws.cell(row=linha, column=1, value=rotulo).fill = PatternFill("solid", fgColor=COR_CATEGORIA[cod])
            ws.cell(row=linha, column=2, value=n)
    linha += 2
    for rotulo, aud in (("Parecer — " + _titulo_execucao(base), base), ("Parecer — " + _titulo_execucao(atual), atual)):
        ws.cell(row=linha, column=1, value=rotulo).font = negrito
        c = ws.cell(row=linha, column=2, value=aud.conclusao_texto or "—")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        linha += 1
    ws.column_dimensions["A"].width = 34
    for col in "BCD":
        ws.column_dimensions[col].width = 30

    ws2 = wb.create_sheet("Evolução da série")
    cabecalho(ws2, 1, ["Execução", "Data", "Situação", "Itens", "Conformes", "NC", "OM", "N/A", "Pendentes", "Índice de conformidade"])
    for r, s in enumerate(comp["serie"], start=2):
        res = s["res"]
        for col, v in enumerate([s["execucao"], f"{s['data']:%d/%m/%Y}", s["aud"].get_status_display(), res["total"],
                                 res["C"], res["NC"], res["OM"], res["NA"], res["P"], _fmt_indice(res["indice"])], start=1):
            ws2.cell(row=r, column=col, value=v)
    for col in range(1, 11):
        ws2.column_dimensions[get_column_letter(col)].width = 16

    ws3 = wb.create_sheet("Itens")
    cabecalho(ws3, 1, ["Tópico", "Auditado", "Solicitação", f"Evidência ({_titulo_execucao(base)})",
                       f"Resultado ({_titulo_execucao(base)})", f"Evidência ({_titulo_execucao(atual)})",
                       f"Resultado ({_titulo_execucao(atual)})", "Evolução"])
    for r, i in enumerate(comp["itens"], start=2):
        ref = i["atual"] or i["base"]
        valores = [ref.topico, ref.auditado, ref.solicitacao,
                   i["base"].evidencia if i["base"] else "—", _txt_classe(i["base"]),
                   i["atual"].evidencia if i["atual"] else "—", _txt_classe(i["atual"]), i["rotulo"]]
        for col, v in enumerate(valores, start=1):
            ws3.cell(row=r, column=col, value=v).alignment = Alignment(wrap_text=True, vertical="top")
        ws3.cell(row=r, column=8).fill = PatternFill("solid", fgColor=COR_CATEGORIA[i["categoria"]])
    for col, w in enumerate([22, 22, 45, 40, 22, 40, 22, 26], start=1):
        ws3.column_dimensions[get_column_letter(col)].width = w
    ws3.freeze_panes = "A2"

    ws4 = wb.create_sheet("Tópicos")
    cabecalho(ws4, 1, ["Tópico", "Auditado(s)", "Itens (antes)", "Itens (depois)", "NC antes", "NC depois",
                       "OM antes", "OM depois", "Conformes antes", "Conformes depois"])
    for r, t in enumerate(comp["topicos"], start=2):
        a, d = t["antes"], t["depois"]
        for col, v in enumerate([t["topico"] or "Sem tópico", ", ".join(t["auditados"]), a["total"], d["total"],
                                 a["NC"], d["NC"], a["OM"], d["OM"], a["C"], d["C"]], start=1):
            ws4.cell(row=r, column=col, value=v)
    for col in range(1, 11):
        ws4.column_dimensions[get_column_letter(col)].width = 18
    ws4.column_dimensions["A"].width = 28
    ws4.column_dimensions["B"].width = 30

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ===================================================================== Word

def gerar_docx(comp):
    atual, base = comp["atual"], comp["base"]
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(0.9)
    sec.top_margin = sec.bottom_margin = Inches(0.8)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    p = doc.add_paragraph()
    r = p.add_run("RELATÓRIO COMPARATIVO DE AUDITORIA")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    p = doc.add_paragraph()
    r = p.add_run(atual.titulo)
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    _titulo_secao(doc, "1. Execuções comparadas")
    _tabela_chave_valor(doc, [
        ("Execução anterior", f"{_titulo_execucao(base)} — {base.get_status_display()}"),
        ("Execução atual", f"{_titulo_execucao(atual)} — {atual.get_status_display()}"),
        ("Objetivo", (atual.objetivo or "—").strip()),
        ("Escopo", (atual.escopo or "—").strip()),
        ("Reavaliação", "Somente itens NC, OM ou pendentes" if atual.somente_pendencias else "Todos os itens"),
    ])

    _titulo_secao(doc, "2. Resumo da evolução")
    tabela = doc.add_table(rows=1, cols=4)
    set_table_borders(tabela)
    for cel, t in zip(tabela.rows[0].cells, ("Classificação", f"Execução {base.execucao}", f"Execução {atual.execucao}", "Variação")):
        _celula(cel, t, negrito=True, cor="FFFFFF")
        set_cell_background(cel, "1F2937")
    for cod in (*CLASSES, "total"):
        cels = tabela.add_row().cells
        _celula(cels[0], ROTULO_CLASSE.get(cod, "Total de itens"), negrito=cod == "total")
        _celula(cels[1], str(comp["res_base"][cod]))
        _celula(cels[2], str(comp["res_atual"][cod]))
        _celula(cels[3], _fmt_delta(comp["deltas"][cod]))
    cels = tabela.add_row().cells
    _celula(cels[0], "Índice de conformidade", negrito=True)
    _celula(cels[1], _fmt_indice(comp["res_base"]["indice"]), negrito=True)
    _celula(cels[2], _fmt_indice(comp["res_atual"]["indice"]), negrito=True)
    _celula(cels[3], _fmt_delta(comp["deltas"]["indice"], pontos=True), negrito=True)
    _larguras(tabela, 2.6, 1.4, 1.4, 1.4)
    nota = doc.add_paragraph()
    run = nota.add_run("Índice de conformidade = conformes ÷ itens classificados (sem N/A e pendentes).")
    run.italic = True
    run.font.size = Pt(9)
    doc.add_paragraph(frase_resumo(comp))

    if len(comp["serie"]) > 2:
        _titulo_secao(doc, "3. Evolução da série")
        serie = doc.add_table(rows=1, cols=6)
        set_table_borders(serie)
        for cel, t in zip(serie.rows[0].cells, ("Execução", "Data", "Itens", "NC", "OM", "Índice")):
            _celula(cel, t, negrito=True, cor="FFFFFF")
            set_cell_background(cel, "1F2937")
        for s in comp["serie"]:
            cels = serie.add_row().cells
            for cel, t in zip(cels, (str(s["execucao"]), f"{s['data']:%d/%m/%Y}", str(s["res"]["total"]),
                                     str(s["res"]["NC"]), str(s["res"]["OM"]), _fmt_indice(s["res"]["indice"]))):
                _celula(cel, t)
        _larguras(serie, 1.0, 1.3, 1.0, 1.0, 1.0, 1.4)

    _titulo_secao(doc, "4. Evolução por tópico")
    tb = doc.add_table(rows=1, cols=5)
    set_table_borders(tb)
    for cel, t in zip(tb.rows[0].cells, ("Tópico / auditado(s)", "NC", "OM", "Conformes", "Itens")):
        _celula(cel, t, negrito=True, cor="FFFFFF")
        set_cell_background(cel, "1F2937")
    for t in comp["topicos"]:
        cels = tb.add_row().cells
        nome = (t["topico"] or "Sem tópico") + (f"\nAuditado(s): {', '.join(t['auditados'])}" if t["auditados"] else "")
        _celula(cels[0], nome)
        for cel, k in zip(cels[1:], ("NC", "OM", "C", "total")):
            _celula(cel, f"{t['antes'][k]} → {t['depois'][k]}")
    _larguras(tb, 2.8, 0.9, 0.9, 1.1, 0.9)

    _titulo_secao(doc, "5. Evolução item a item")
    if not comp["itens"]:
        doc.add_paragraph("Nenhum item para comparar.")
    for cod in ORDEM_CATEGORIAS:
        grupo = [i for i in comp["itens"] if i["categoria"] == cod]
        if not grupo:
            continue
        p = doc.add_paragraph()
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(8)
        run = p.add_run(f"{grupo[0]['rotulo']} ({len(grupo)})")
        run.bold = True
        run.font.size = Pt(11)
        tab = doc.add_table(rows=1, cols=3)
        set_table_borders(tab)
        for cel, t in zip(tab.rows[0].cells, ("Item", f"Execução {base.execucao}", f"Execução {atual.execucao}")):
            _celula(cel, t, negrito=True)
            set_cell_background(cel, COR_CATEGORIA[cod])
        for i in grupo:
            ref = i["atual"] or i["base"]
            cels = tab.add_row().cells
            cab = ref.solicitacao + (f"\n{ref.topico}" if ref.topico else "") + (f" · {ref.auditado}" if ref.auditado else "")
            _celula(cels[0], cab)
            for cel, linha in ((cels[1], i["base"]), (cels[2], i["atual"])):
                _celula(cel, _txt_classe(linha) + (f"\n{linha.evidencia.strip()}" if linha is not None and linha.evidencia.strip() else ""))
        _larguras(tab, 3.0, 1.9, 1.9)

    _titulo_secao(doc, "6. Pareceres")
    for aud in (base, atual):
        p = doc.add_paragraph()
        run = p.add_run(_titulo_execucao(aud))
        run.bold = True
        doc.add_paragraph((aud.conclusao_texto or "").strip() or "—")

    saida = io.BytesIO()
    doc.save(saida)
    saida.seek(0)
    return saida
