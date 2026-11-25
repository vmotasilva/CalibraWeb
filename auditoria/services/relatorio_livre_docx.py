"""Relatório Word (.docx) da Auditoria Livre.

Estrutura: identificação, resumo dos resultados, conclusão e os achados agrupados por
classificação (NC, OM, Conformes, Não aplicáveis, Pendentes), com as fotos de cada evidência.
"""
import base64
import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor


def set_cell_background(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex.replace("#", "").upper()}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tc_mar = OxmlElement("w:tcMar")
    for lado, valor in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        no = OxmlElement(f"w:{lado}")
        no.set(qn("w:w"), str(valor))
        no.set(qn("w:type"), "dxa")
        tc_mar.append(no)
    cell._tc.get_or_add_tcPr().append(tc_mar)


def set_table_borders(table, color="CBD5E1", sz="4"):
    lados = "".join(
        f'<w:{l} w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        for l in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    table._tbl.tblPr.append(parse_xml(f'<w:tblBorders {nsdecls("w")}>{lados}</w:tblBorders>'))

COR_CLASSE = {
    "NC": ("DC2626", "FFFFFF"),
    "OM": ("F59E0B", "3D2E00"),
    "C": ("16A34A", "FFFFFF"),
    "NA": ("6B7280", "FFFFFF"),
    "P": ("374151", "FFFFFF"),
}
# Ordem de apresentação dos achados
GRUPOS = [
    ("NC", "Não Conformidades"),
    ("OM", "Oportunidades de Melhoria"),
    ("C", "Conformidades"),
    ("NA", "Não Aplicáveis"),
    ("P", "Pendentes de classificação"),
]


def _texto(valor):
    return (valor or "").strip() or "—"


def _celula(cell, texto, negrito=False, cor=None, tamanho=10):
    cell.text = ""
    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    run = cell.paragraphs[0].add_run(texto)
    run.bold = negrito
    run.font.size = Pt(tamanho)
    if cor:
        run.font.color.rgb = RGBColor.from_string(cor)
    set_cell_margins(cell)


def _titulo_secao(doc, texto):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(texto)
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)


def _larguras(tabela, *polegadas):
    """Fixa as larguras (o Word e o LibreOffice ignoram a largura só da célula com autofit ligado)."""
    tabela.autofit = False
    for col, w in zip(tabela.columns, polegadas):
        col.width = Inches(w)
        for cel in col.cells:
            cel.width = Inches(w)


def _manter_junto(tabela):
    """Impede quebra de página entre as linhas da tabela e a que vem a seguir."""
    for row in tabela.rows:
        for cel in row.cells:
            for par in cel.paragraphs:
                par.paragraph_format.keep_with_next = True


def _tabela_chave_valor(doc, linhas):
    tabela = doc.add_table(rows=0, cols=2)
    set_table_borders(tabela)
    for chave, valor in linhas:
        cels = tabela.add_row().cells
        _celula(cels[0], chave, negrito=True)
        set_cell_background(cels[0], "F1F5F9")
        _celula(cels[1], valor)
    _larguras(tabela, 1.8, 4.7)
    return tabela


def _fotos(doc, imagens):
    """Insere até 2 fotos por linha, cada uma com sua legenda."""
    for i in range(0, len(imagens), 2):
        tabela = doc.add_table(rows=1, cols=2)
        for cel, img in zip(tabela.rows[0].cells, imagens[i:i + 2]):
            try:
                dados = base64.b64decode(img.arquivo_base64)
                cel.paragraphs[0].add_run().add_picture(io.BytesIO(dados), width=Inches(3.0))
            except Exception:
                cel.paragraphs[0].add_run("(foto indisponível)").italic = True
            legenda = cel.add_paragraph(img.legenda or "")
            legenda.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in legenda.runs:
                r.font.size = Pt(9)
                r.italic = True
        doc.add_paragraph()


def _achado(doc, numero, sol):
    cor_fundo, cor_texto = COR_CLASSE.get(sol.conclusao, COR_CLASSE["P"])
    rotulo = sol.get_conclusao_display()
    if sol.conclusao == "NC" and sol.grau_nc:
        rotulo += f" ({sol.get_grau_nc_display()})"

    cab = doc.add_table(rows=1, cols=2)
    set_table_borders(cab)
    c0, c1 = cab.rows[0].cells
    titulo = f"#{numero}" + (f"  ·  {sol.topico}" if sol.topico else "") + (
        f"  ·  Auditado: {sol.auditado}" if sol.auditado else "")
    _celula(c0, titulo, negrito=True, cor=cor_texto)
    _celula(c1, rotulo, negrito=True, cor=cor_texto)
    c1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for c in (c0, c1):
        set_cell_background(c, cor_fundo)
    _larguras(cab, 4.2, 2.3)
    _manter_junto(cab)

    linhas = [("Evidência solicitada", _texto(sol.solicitacao)), ("Evidência apresentada", _texto(sol.evidencia))]
    if (sol.observacao or "").strip():
        linhas.append(("Observação do auditor", sol.observacao.strip()))
    if sol.conclusao in ("NC", "OM") and (
        sol.capa_status != "PENDENTE" or sol.capa_causa_raiz or sol.capa_acao_corretiva
    ):
        linhas.append(("Plano de ação — situação", sol.get_capa_status_display()))
        linhas.append(("Causa raiz", _texto(sol.capa_causa_raiz)))
        linhas.append(("Ação corretiva / preventiva", _texto(sol.capa_acao_corretiva)))
        linhas.append(("Responsável", _texto(sol.capa_responsavel)))
        linhas.append(("Prazo", sol.capa_prazo.strftime("%d/%m/%Y") if sol.capa_prazo else "—"))
        if (sol.capa_parecer_auditor or "").strip():
            linhas.append(("Parecer do auditor", sol.capa_parecer_auditor.strip()))
    _manter_junto(_tabela_chave_valor(doc, linhas))

    imagens = list(sol.imagens.all())
    if imagens:
        doc.add_paragraph()
        _fotos(doc, imagens)
    else:
        doc.add_paragraph()


def _resumo_topico(itens):
    """Ex.: "4 itens: 1 NC, 1 OM, 2 conformes" para o cabeçalho de um tópico."""
    c = {cod: 0 for cod, _ in GRUPOS}
    for _, s in itens:
        c[s.conclusao] += 1
    partes = [f"{c[cod]} {rot}" for cod, rot in (("NC", "NC"), ("OM", "OM"), ("C", "conformes"), ("NA", "N/A"), ("P", "pendentes")) if c[cod]]
    return f"{len(itens)} {'item' if len(itens) == 1 else 'itens'}: " + ", ".join(partes)


def _achados_por_topico(doc, numeradas):
    """Achados agrupados por tópico (cada um com os auditados), mantendo a numeração da auditoria."""
    topicos, ordem = {}, []
    for n, s in numeradas:
        chave = s.topico or ""
        if chave not in topicos:
            topicos[chave] = []
            ordem.append(chave)
        topicos[chave].append((n, s))
    # tópicos em ordem alfabética; "sem tópico" por último
    for chave in sorted(ordem, key=lambda t: (t == "", t.casefold())):
        itens = topicos[chave]
        auditados = []
        for _, s in itens:
            if s.auditado and s.auditado not in auditados:
                auditados.append(s.auditado)
        p = doc.add_paragraph()
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(10)
        run = p.add_run(chave or "Sem tópico")
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        info = doc.add_paragraph()
        info.paragraph_format.keep_with_next = True
        txt = _resumo_topico(itens) + (f"  ·  Auditado(s): {', '.join(auditados)}" if auditados else "")
        r = info.add_run(txt)
        r.italic = True
        r.font.size = Pt(9)
        for n, s in itens:
            _achado(doc, n, s)


def gerar_relatorio_livre_docx(auditoria, solicitacoes, agrupar="classificacao"):
    """Retorna um BytesIO com o relatório. `solicitacoes` em ordem cronológica, com imagens prefetch.

    agrupar: "classificacao" (NC, OM, Conformes…) ou "topico" (um bloco por tópico, com o auditado).
    """
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(1)
    sec.top_margin = sec.bottom_margin = Inches(0.9)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    p = doc.add_paragraph()
    r = p.add_run("RELATÓRIO DE AUDITORIA")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)
    p = doc.add_paragraph()
    r = p.add_run(auditoria.titulo)
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    periodo = f"{auditoria.data_inicio:%d/%m/%Y}"
    if auditoria.data_fim:
        periodo += f" a {auditoria.data_fim:%d/%m/%Y}"
    auditores = ", ".join(u.get_full_name() or u.get_username() for u in auditoria.auditores.all())
    _titulo_secao(doc, "1. Identificação")
    _tabela_chave_valor(doc, [
        ("Objetivo", _texto(auditoria.objetivo)),
        ("Escopo", _texto(auditoria.escopo)),
        ("Critério / Referência", _texto(auditoria.criterio)),
        ("Local / Setor / Processo", _texto(auditoria.local)),
        ("Período", periodo),
        ("Auditor líder", _texto(auditoria.auditor_lider)),
        ("Auditores", _texto(auditores)),
        ("Auditados / Entrevistados", _texto(auditoria.auditados)),
        ("Situação", auditoria.get_status_display()),
        ("Execução", str(auditoria.execucao)),
    ])

    contagem = {c: 0 for c, _ in GRUPOS}
    for s in solicitacoes:
        contagem[s.conclusao] += 1
    classificados = contagem["C"] + contagem["NC"] + contagem["OM"]
    _titulo_secao(doc, "2. Resumo dos resultados")
    tabela = doc.add_table(rows=1, cols=2)
    set_table_borders(tabela)
    for cel, txt in zip(tabela.rows[0].cells, ("Classificação", "Quantidade")):
        _celula(cel, txt, negrito=True, cor="FFFFFF")
        set_cell_background(cel, "1F2937")
    for cod, nome in GRUPOS:
        cels = tabela.add_row().cells
        _celula(cels[0], nome)
        _celula(cels[1], str(contagem[cod]))
    cels = tabela.add_row().cells
    _celula(cels[0], "Total de evidências solicitadas", negrito=True)
    _celula(cels[1], str(len(solicitacoes)), negrito=True)
    _larguras(tabela, 4.8, 1.7)
    if classificados:
        pct = contagem["C"] * 100 / classificados
        nota = doc.add_paragraph()
        run = nota.add_run(
            f"Índice de conformidade: {pct:.0f}% ({contagem['C']} de {classificados} evidências classificadas, "
            "excluindo não aplicáveis e pendentes)."
        )
        run.italic = True
        run.font.size = Pt(9)

    _titulo_secao(doc, "3. Conclusão / Parecer")
    doc.add_paragraph(_texto(auditoria.conclusao_texto))

    numeradas = list(enumerate(solicitacoes, start=1))
    _titulo_secao(doc, "4. Achados")
    if not numeradas:
        doc.add_paragraph("Nenhuma evidência foi solicitada nesta auditoria.")
    if agrupar == "topico":
        _achados_por_topico(doc, numeradas)
    else:
        for cod, nome in GRUPOS:
            grupo = [(n, s) for n, s in numeradas if s.conclusao == cod]
            if not grupo:
                continue
            p = doc.add_paragraph()
            p.paragraph_format.keep_with_next = True
            run = p.add_run(f"{nome} ({len(grupo)})")
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor.from_string(COR_CLASSE[cod][0])
            for n, s in grupo:
                _achado(doc, n, s)


    saida = io.BytesIO()
    doc.save(saida)
    saida.seek(0)
    return saida
