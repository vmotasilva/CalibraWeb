import os
import io
import re
import base64
from typing import Optional, List, Dict, Any
from django.conf import settings
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
from bs4 import BeautifulSoup
from PIL import Image as PILImage


def natural_sort_key(s: str):
    """Ordenação natural para referências como 4.1, 4.1.1, 4.10, etc."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s or ""))]


def set_cell_background(cell, color_hex: str):
    """Aplica cor de fundo a uma célula de tabela docx via XML."""
    color_hex = color_hex.replace("#", "").upper()
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Define margens internas (padding) de uma célula docx em dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    """Aplica bordas suaves personalizadas a uma tabela docx."""
    tblPr = table._tbl.tblPr
    borders_xml = f'''
    <w:tblBorders {nsdecls("w")}>
        <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
    </w:tblBorders>
    '''
    tblPr.append(parse_xml(borders_xml))


def get_template_docx_path() -> str:
    """Retorna o caminho do template docx no servidor."""
    base_dir = getattr(settings, 'BASE_DIR', None)
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    templates_dir = os.path.join(str(base_dir), 'auditoria', 'templates_docx')
    try:
        os.makedirs(templates_dir, exist_ok=True)
    except OSError:
        pass
    return os.path.join(templates_dir, 'relatorio_auditoria_template.docx')


def inject_html_to_docx(doc: Document, html_content: str, parent_element=None):
    """
    Converte código HTML (do editor WYSIWYG Quill/TinyMCE) nativamente em parágrafos,
    títulos, listas, tabelas e imagens no documento Word.
    """
    if not html_content or not html_content.strip():
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run("Nenhuma síntese ou observação registrada pelo auditor líder.")
        run.font.italic = True
        run.font.color.rgb = RGBColor(100, 116, 139)
        return

    soup = BeautifulSoup(html_content, 'html.parser')

    def process_inline(node, p):
        for child in node.children:
            if child.name is None:
                text = str(child)
                if text:
                    p.add_run(text)
            elif child.name in ['strong', 'b']:
                r = p.add_run(child.get_text())
                r.bold = True
            elif child.name in ['em', 'i']:
                r = p.add_run(child.get_text())
                r.italic = True
            elif child.name == 'u':
                r = p.add_run(child.get_text())
                r.underline = True
            elif child.name == 'a':
                r = p.add_run(child.get_text())
                r.font.color.rgb = RGBColor(37, 99, 235)
                r.underline = True
            elif child.name == 'code':
                r = p.add_run(child.get_text())
                r.font.name = 'Consolas'
                r.font.size = Pt(9.5)
            elif child.name == 'img':
                src = child.get('src', '')
                if src:
                    insert_image_to_docx(doc, src, p)
            elif child.name == 'br':
                p.add_run('\n')
            else:
                process_inline(child, p)

    def insert_image_to_docx(doc_obj, src, target_paragraph=None):
        try:
            pil_img = None
            if src.startswith('data:image'):
                b64_data = src.split(',', 1)[1] if ',' in src else src
                img_bytes = base64.b64decode(b64_data)
                pil_img = PILImage.open(io.BytesIO(img_bytes))
            elif os.path.exists(src):
                pil_img = PILImage.open(src)

            if pil_img:
                if pil_img.mode in ('RGBA', 'P', 'LA'):
                    pil_img = pil_img.convert('RGB')
                
                # Redimensiona mantendo proporção até 5.8 polegadas de largura
                max_w_px = 650
                if pil_img.width > max_w_px:
                    ratio = max_w_px / float(pil_img.width)
                    new_h = int(float(pil_img.height) * ratio)
                    pil_img = pil_img.resize((max_w_px, new_h), PILImage.Resampling.LANCZOS)

                img_io = io.BytesIO()
                pil_img.save(img_io, format='JPEG', quality=88)
                img_io.seek(0)

                img_p = target_paragraph if target_paragraph is not None else doc_obj.add_paragraph()
                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                img_p.paragraph_format.space_before = Pt(6)
                img_p.paragraph_format.space_after = Pt(8)
                img_p.add_run().add_picture(img_io, width=Inches(min(5.6, pil_img.width / 110.0)))
        except Exception:
            pass

    for elem in soup.find_all(recursive=False):
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(elem.name[1])
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.keep_with_next = True
            
            font_size = {1: 14, 2: 13, 3: 12, 4: 11, 5: 10, 6: 10}.get(level, 12)
            r = p.add_run(elem.get_text().strip())
            r.bold = True
            r.font.size = Pt(font_size)
            r.font.color.rgb = RGBColor(15, 23, 42)

        elif elem.name in ['p', 'div']:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.15
            process_inline(elem, p)

        elif elem.name in ['ul', 'ol']:
            is_ordered = (elem.name == 'ol')
            for idx, li in enumerate(elem.find_all('li', recursive=False), 1):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.25)
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(2)
                
                prefix = f"{idx}. " if is_ordered else "• "
                r_prefix = p.add_run(prefix)
                r_prefix.bold = True
                r_prefix.font.color.rgb = RGBColor(37, 99, 235)
                process_inline(li, p)

        elif elem.name == 'blockquote':
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run(elem.get_text().strip())
            r.italic = True
            r.font.color.rgb = RGBColor(71, 85, 105)

        elif elem.name == 'table':
            rows = elem.find_all('tr')
            if rows:
                num_cols = max(len(r.find_all(['td', 'th'])) for r in rows)
                t = doc.add_table(rows=len(rows), cols=num_cols)
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                set_table_borders(t, color="CBD5E1")
                
                for r_idx, r_tag in enumerate(rows):
                    cells = r_tag.find_all(['td', 'th'])
                    is_header_row = (r_idx == 0 or any(c.name == 'th' for c in cells))
                    for c_idx, c_tag in enumerate(cells):
                        if c_idx < num_cols:
                            cell = t.cell(r_idx, c_idx)
                            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
                            p = cell.paragraphs[0]
                            p.paragraph_format.space_before = Pt(1)
                            p.paragraph_format.space_after = Pt(1)
                            process_inline(c_tag, p)
                            if is_header_row:
                                set_cell_background(cell, "F1F5F9")
                                for run in p.runs:
                                    run.bold = True
                                    run.font.size = Pt(9.5)
                            else:
                                for run in p.runs:
                                    run.font.size = Pt(9.0)

        elif elem.name == 'img':
            src = elem.get('src', '')
            if src:
                insert_image_to_docx(doc, src)


def build_resumo_area_funcional_data(auditoria) -> List[Dict[str, Any]]:
    """
    Agrupa Não Conformidades (NC) e Oportunidades de Melhoria (OM) por Área Funcional / Seção da Norma.
    Colunas esperadas: Área/Processo | Gaps | Evidência | Descrição da avaliação
    """
    from ..models import (
        ItemNorma,
        RespostaEntrevistaIso,
        AvaliacaoFinalRequisitoIso,
    )

    itens_escopo = auditoria.escopo_itens.all()
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related(
        'solicitacoes', 'solicitacoes__imagens', 'pergunta__itens_norma'
    )
    respostas_map = {r.pergunta_id: r for r in respostas}
    avaliacoes_finais = {av.item_norma_id: av for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)}

    # Mapeia perguntas para itens
    pergunta_itens_map = {}
    for ag in auditoria.agendas.all():
        for p in ag.perguntas.all():
            if p.id not in pergunta_itens_map:
                pergunta_itens_map[p.id] = set(it.id for it in p.itens_norma.all())

    gaps_por_area = {}

    for item in itens_escopo:
        av_final = avaliacoes_finais.get(item.id)
        perguntas_do_item = [p_id for p_id, ids in pergunta_itens_map.items() if item.id in ids]
        sols_do_item = []
        for p_id in perguntas_do_item:
            r = respostas_map.get(p_id)
            if r:
                for s in r.solicitacoes.all():
                    sols_do_item.append(s)

        # Determina status
        if av_final and av_final.classificacao:
            status = av_final.classificacao
        elif sols_do_item:
            conclusoes = [s.conclusao for s in sols_do_item]
            if 'NC' in conclusoes:
                status = 'NC'
            elif 'OM' in conclusoes:
                status = 'OM'
            else:
                status = 'C'
        else:
            status = 'C'

        if status in ['NC', 'OM']:
            # Extrai a área/seção macro (ex: "4 - Sistema de Gestão", "7 - Realização do Produto")
            ref_parts = item.referencia.split('.')
            sec_code = ref_parts[0] if ref_parts else item.referencia
            
            # Tenta buscar item pai para o nome da macroárea
            pai = ItemNorma.objects.filter(norma=auditoria.norma, referencia=sec_code).first()
            area_nome = f"Seção {sec_code} - {pai.titulo if pai else item.titulo}"

            # Identifica grau se for NC
            if status == 'NC':
                grau = "NC Maior" if (av_final and av_final.grau_nc == 'MAIOR') else "NC Menor"
                gap_badge = f"{grau} (Item {item.referencia})"
                tipo_gap = 'NC'
            else:
                gap_badge = f"Oportunidade de Melhoria (Item {item.referencia})"
                tipo_gap = 'OM'

            # Evidências e Amostras
            evid_list = []
            for s in sols_do_item:
                s_nome = (s.solicitacao or "").strip()
                s_ev = (s.evidencia or "").strip()
                imgs_count = len(s.imagens.all()) if hasattr(s, 'imagens') else 0
                img_tag = f" [📷 {imgs_count} foto(s)]" if imgs_count > 0 else ""
                
                if s_nome and s_ev:
                    evid_list.append(f"• {s_nome}: {s_ev}{img_tag}")
                elif s_nome:
                    evid_list.append(f"• {s_nome}{img_tag}")
                elif s_ev:
                    evid_list.append(f"• {s_ev}{img_tag}")

            if not evid_list:
                for p_id in perguntas_do_item:
                    r = respostas_map.get(p_id)
                    if r and r.texto_resposta:
                        evid_list.append(f"• {r.texto_resposta.strip()}")

            evidencia_str = "\n".join(evid_list) if evid_list else "Amostragem realizada durante a entrevista de auditoria."

            # Descrição da avaliação
            desc_list = []
            if av_final and av_final.justificativa:
                desc_list.append(av_final.justificativa.strip())
            for s in sols_do_item:
                if s.conclusao == 'OBS' and s.evidencia:
                    desc_list.append(f"Observação do auditor: {s.evidencia.strip()}")
            if not desc_list:
                desc_list.append(f"Desvio identificado em relação aos critérios do requisito {item.referencia} da norma {auditoria.norma.codigo}.")

            descricao_str = "\n".join(desc_list)

            if area_nome not in gaps_por_area:
                gaps_por_area[area_nome] = []

            gaps_por_area[area_nome].append({
                'area': area_nome,
                'item_referencia': item.referencia,
                'item_titulo': item.titulo,
                'tipo': tipo_gap,
                'gaps': gap_badge,
                'evidencia': evidencia_str,
                'descricao': descricao_str
            })

    # Lista final achatada e agrupada por área
    resultado = []
    for area_nome in sorted(gaps_por_area.keys(), key=natural_sort_key):
        for gap in gaps_por_area[area_nome]:
            resultado.append(gap)

    return resultado


def create_base_template_docx(auditoria) -> Document:
    """
    Cria uma estrutura de documento Word profissional e formatada em memória
    caso não haja arquivo template em disco.
    """
    doc = Document()

    # Configuração de Margens (A4)
    sections = doc.sections
    for s in sections:
        s.page_height = Inches(11.69)
        s.page_width = Inches(8.27)
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.9)
        s.right_margin = Inches(0.9)

    return doc


def generate_relatorio_docx_buffer(auditoria) -> io.BytesIO:
    """
    Gera o Relatório de Auditoria Interna completo em formato DOCX com:
    1. Metadados do Cabeçalho e Identificação
    2. Tabela Nativa de Avaliação Geral (Resultados, Contagens e Veredicto)
    3. Síntese da Auditoria (Processamento HTML rico com imagens e tabelas)
    4. Tabela de Resumo por Área Funcional (Agrupada com Gaps, Evidências e Descrição)
    5. Pontos Fortes e Oportunidades
    6. Conclusão e Assinaturas
    """
    from ..models import (
        ItemNorma,
        RespostaEntrevistaIso,
        AvaliacaoFinalRequisitoIso,
    )

    doc = create_base_template_docx(auditoria)

    # Cores do Sistema
    NAVY_HEX = "0B2545"
    BLUE_HEX = "134074"
    LIGHT_BG_HEX = "F8FAFC"
    BORDER_HEX = "CBD5E1"

    # =========================================================================
    # 1. CABEÇALHO / BANNER DO RELATÓRIO
    # =========================================================================
    header_table = doc.add_table(rows=1, cols=1)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_h = header_table.cell(0, 0)
    set_cell_background(cell_h, NAVY_HEX)
    set_cell_margins(cell_h, top=140, bottom=140, left=180, right=180)
    
    p_top = cell_h.paragraphs[0]
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_top.paragraph_format.space_before = Pt(0)
    p_top.paragraph_format.space_after = Pt(2)
    r_top = p_top.add_run("RELATÓRIO DE AUDITORIA INTERNA DA QUALIDADE")
    r_top.bold = True
    r_top.font.size = Pt(15)
    r_top.font.color.rgb = RGBColor(255, 255, 255)

    p_sub = cell_h.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(0)
    norma_desc = getattr(auditoria.norma, 'descricao', '') or ''
    norma_str = f"Norma de Referência: {auditoria.norma.codigo}" + (f" — {norma_desc}" if norma_desc else "")
    r_sub = p_sub.add_run(norma_str)
    r_sub.font.size = Pt(10)
    r_sub.font.color.rgb = RGBColor(226, 232, 240)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # =========================================================================
    # 2. METADADOS E INFORMAÇÕES DA AUDITORIA
    # =========================================================================
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(meta_table, color=BORDER_HEX)

    unidade_str = getattr(auditoria, 'empresa_auditada', '') or "Tecnolens"
    auditores_list = [a.get_full_name() or a.username for a in auditoria.auditores.all()]
    auditores_str = ", ".join(auditores_list) if auditores_list else (auditoria.abertura_auditores or "Equipe Auditora Designada")
    
    dt_ini = auditoria.data_inicio.strftime('%d/%m/%Y') if auditoria.data_inicio else ""
    dt_fim = auditoria.data_fim.strftime('%d/%m/%Y') if auditoria.data_fim else ""
    datas_str = f"{dt_ini} a {dt_fim}" if (dt_ini and dt_fim and dt_ini != dt_fim) else (dt_ini or dt_fim or "Em andamento")
    rep_str = auditoria.encerramento_representantes or auditoria.abertura_representantes or "Representantes da Unidade Auditada"

    meta_data = [
        ("Unidade / Empresa:", unidade_str, "Data da Auditoria:", datas_str),
        ("Auditor(es) Líder(es):", auditores_str, "Representantes Auditados:", rep_str),
        ("Escopo da Auditoria:", f"{auditoria.norma.codigo}" + (f" - {norma_desc}" if norma_desc else " - Sistema de Gestão"), "Modalidade:", "Presencial e Amostragem Documental"),
        ("Status do Ciclo:", auditoria.get_status_display() if hasattr(auditoria, 'get_status_display') else "Concluída", "Data do Relatório:", dt_fim or dt_ini or "Hoje"),
    ]

    for r_idx, (k1, v1, k2, v2) in enumerate(meta_data):
        c0 = meta_table.cell(r_idx, 0)
        c1 = meta_table.cell(r_idx, 1)
        set_cell_margins(c0, top=60, bottom=60, left=100, right=100)
        set_cell_margins(c1, top=60, bottom=60, left=100, right=100)
        set_cell_background(c0, LIGHT_BG_HEX if r_idx % 2 == 0 else "FFFFFF")
        set_cell_background(c1, LIGHT_BG_HEX if r_idx % 2 == 0 else "FFFFFF")

        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r_k1 = p0.add_run(f"{k1} ")
        r_k1.bold = True
        r_k1.font.size = Pt(9)
        r_v1 = p0.add_run(str(v1))
        r_v1.font.size = Pt(9)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r_k2 = p1.add_run(f"{k2} ")
        r_k2.bold = True
        r_k2.font.size = Pt(9)
        r_v2 = p1.add_run(str(v2))
        r_v2.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # =========================================================================
    # 3. SNAPSHOT DA AVALIAÇÃO GERAL (TABELA DE RESULTADOS NATIVA NO WORD)
    # =========================================================================
    sec_title = doc.add_paragraph()
    sec_title.paragraph_format.space_before = Pt(8)
    sec_title.paragraph_format.space_after = Pt(4)
    r_sec = sec_title.add_run("1. AVALIAÇÃO GERAL E RESULTADOS DA AUDITORIA")
    r_sec.bold = True
    r_sec.font.size = Pt(12)
    r_sec.font.color.rgb = RGBColor(11, 37, 69)

    # Coleta de métricas e status
    itens_escopo = list(auditoria.escopo_itens.all())
    respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related('solicitacoes', 'pergunta__itens_norma')
    respostas_map = {r.pergunta_id: r for r in respostas}
    avaliacoes_finais = {av.item_norma_id: av for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)}

    count_c, count_nc_menor, count_nc_maior, count_om, count_na, count_p = 0, 0, 0, 0, 0, 0
    
    for it in itens_escopo:
        av = avaliacoes_finais.get(it.id)
        if av and av.classificacao:
            st = av.classificacao
            if st == 'NC':
                if av.grau_nc == 'MAIOR':
                    count_nc_maior += 1
                else:
                    count_nc_menor += 1
            elif st == 'C': count_c += 1
            elif st == 'OM': count_om += 1
            elif st == 'NA': count_na += 1
            else: count_p += 1
        else:
            # Avaliação via solicitações
            sols = []
            for r in respostas.filter(pergunta__itens_norma=it):
                sols.extend(list(r.solicitacoes.all()))
            if sols:
                concs = [s.conclusao for s in sols]
                if 'NC' in concs:
                    if any(s.grau_nc == 'MAIOR' for s in sols if s.conclusao == 'NC'):
                        count_nc_maior += 1
                    else:
                        count_nc_menor += 1
                elif 'OM' in concs: count_om += 1
                elif any(c in ['C', 'OBS'] for c in concs): count_c += 1
                elif all(c == 'NA' for c in concs): count_na += 1
                else: count_p += 1
            else:
                count_c += 1

    total_avaliados = count_c + count_om + count_nc_menor + count_nc_maior
    pct_conformidade = round((count_c / total_avaliados * 100), 1) if total_avaliados > 0 else 0.0

    # Tabela 2 Colunas: Lado A (Resultados numéricos), Lado B (Card de Índice & Veredito)
    res_table = doc.add_table(rows=7, cols=4)
    res_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(res_table, color=BORDER_HEX)

    # Cabeçalho da tabela de contagem
    hdr_cells = [("Bandeira / Classificação", "Sigla", "Qtd", "% Base")]
    rows_data = [
        ("Conforme", "C", count_c, f"{(count_c/total_avaliados*100):.1f}%" if total_avaliados else "0%", "DCFCE7", "166534"),
        ("Não Conformidade Menor", "NC Menor", count_nc_menor, f"{(count_nc_menor/total_avaliados*100):.1f}%" if total_avaliados else "0%", "FEE2E2", "991B1B"),
        ("Não Conformidade Maior", "NC Maior", count_nc_maior, f"{(count_nc_maior/total_avaliados*100):.1f}%" if total_avaliados else "0%", "FEE2E2", "991B1B"),
        ("Oportunidade de Melhoria", "OM", count_om, f"{(count_om/total_avaliados*100):.1f}%" if total_avaliados else "0%", "FEF9C3", "854D0E"),
        ("Não Aplicável (fora do escopo)", "NA", count_na, "-", "F3F4F6", "475569"),
        ("Total de Requisitos Avaliados", "TOTAL", total_avaliados, "100.0%", "F1F5F9", "0F172A"),
    ]

    # Preenche Linha 0 (Header)
    for c_idx, h_text in enumerate(["Classificação", "Sigla", "Qtd", "% Total"]):
        c = res_table.cell(0, c_idx)
        set_cell_background(c, NAVY_HEX)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, (label, sigla, qtd, pct, bg_hex, text_hex) in enumerate(rows_data, 1):
        c0 = res_table.cell(r_idx, 0)
        c1 = res_table.cell(r_idx, 1)
        c2 = res_table.cell(r_idx, 2)
        c3 = res_table.cell(r_idx, 3)

        for cell in [c0, c1, c2, c3]:
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)

        # C0 Label
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(label)
        r0.font.size = Pt(9)
        if r_idx == 6: r0.bold = True

        # C1 Sigla
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p1.paragraph_format.space_after = Pt(0)
        set_cell_background(c1, bg_hex)
        r1 = p1.add_run(sigla)
        r1.bold = True
        r1.font.size = Pt(9)
        r_color = RGBColor(int(text_hex[:2], 16), int(text_hex[2:4], 16), int(text_hex[4:], 16))
        r1.font.color.rgb = r_color

        # C2 Qtd
        p2 = c2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_after = Pt(0)
        r2 = p2.add_run(str(qtd))
        r2.bold = True
        r2.font.size = Pt(9)

        # C3 Pct
        p3 = c3.paragraphs[0]
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p3.paragraph_format.space_after = Pt(0)
        r3 = p3.add_run(pct)
        r3.font.size = Pt(9)
        if r_idx == 6: r3.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Card Índice de Conformidade e Parecer
    veredito_status = "ADEQUADO" if (count_nc_maior == 0 and count_nc_menor <= 2) else ("MELHORIA NECESSÁRIA" if count_nc_maior <= 3 else "INADEQUADO")
    card_table = doc.add_table(rows=1, cols=2)
    card_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(card_table, color="16A34A" if veredito_status == "ADEQUADO" else ("D97706" if veredito_status == "MELHORIA NECESSÁRIA" else "DC2626"))

    cell_score = card_table.cell(0, 0)
    set_cell_background(cell_score, "DCFCE7" if veredito_status == "ADEQUADO" else ("FEF9C3" if veredito_status == "MELHORIA NECESSÁRIA" else "FEE2E2"))
    set_cell_margins(cell_score, top=100, bottom=100, left=140, right=140)
    
    p_sc = cell_score.paragraphs[0]
    p_sc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sc.paragraph_format.space_after = Pt(0)
    r_sc_lbl = p_sc.add_run("ÍNDICE GERAL DE CONFORMIDADE\n")
    r_sc_lbl.bold = True
    r_sc_lbl.font.size = Pt(8.5)
    r_sc_lbl.font.color.rgb = RGBColor(71, 85, 105)
    r_sc_val = p_sc.add_run(f"{pct_conformidade}%\n")
    r_sc_val.bold = True
    r_sc_val.font.size = Pt(20)
    r_sc_val.font.color.rgb = RGBColor(22, 101, 52) if veredito_status == "ADEQUADO" else RGBColor(180, 83, 9)

    cell_ver = card_table.cell(0, 1)
    set_cell_background(cell_ver, LIGHT_BG_HEX)
    set_cell_margins(cell_ver, top=100, bottom=100, left=140, right=140)
    p_v = cell_ver.paragraphs[0]
    p_v.paragraph_format.space_after = Pt(2)
    r_v_lbl = p_v.add_run("PARECER / VEREDITO DA AUDITORIA:\n")
    r_v_lbl.bold = True
    r_v_lbl.font.size = Pt(8.5)
    r_v_lbl.font.color.rgb = RGBColor(71, 85, 105)
    r_v_tit = p_v.add_run(f"{veredito_status}\n")
    r_v_tit.bold = True
    r_v_tit.font.size = Pt(12)
    r_v_tit.font.color.rgb = RGBColor(22, 101, 52) if veredito_status == "ADEQUADO" else RGBColor(180, 83, 9)
    
    r_v_txt = p_v.add_run(
        "O Sistema de Gestão da Qualidade atende aos requisitos normativos e demonstra maturidade operacional." if veredito_status == "ADEQUADO"
        else "O Sistema de Gestão da Qualidade requer a elaboração de Planos de Ação Corretiva para os desvios pontuais identificados."
    )
    r_v_txt.font.size = Pt(8.5)
    r_v_txt.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # =========================================================================
    # 4. SÍNTESE DA AUDITORIA (CONVERSOR HTML PARA DOCX NATIVO)
    # =========================================================================
    sec2_title = doc.add_paragraph()
    sec2_title.paragraph_format.space_before = Pt(8)
    sec2_title.paragraph_format.space_after = Pt(4)
    r_sec2 = sec2_title.add_run("2. SÍNTESE EXECUTIVA DA AUDITORIA")
    r_sec2.bold = True
    r_sec2.font.size = Pt(12)
    r_sec2.font.color.rgb = RGBColor(11, 37, 69)

    sintese_html = getattr(auditoria, 'sintese', '') or ""
    inject_html_to_docx(doc, sintese_html)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # =========================================================================
    # 5. RESUMO DA AUDITORIA POR ÁREA FUNCIONAL (TABELA AGRUPADA)
    # =========================================================================
    sec3_title = doc.add_paragraph()
    sec3_title.paragraph_format.space_before = Pt(8)
    sec3_title.paragraph_format.space_after = Pt(4)
    r_sec3 = sec3_title.add_run("3. RESUMO DA AUDITORIA POR ÁREA FUNCIONAL (GAPS & OPORTUNIDADES)")
    r_sec3.bold = True
    r_sec3.font.size = Pt(12)
    r_sec3.font.color.rgb = RGBColor(11, 37, 69)

    resumo_gaps = build_resumo_area_funcional_data(auditoria)

    if resumo_gaps:
        # Colunas: Área/Processo | Gaps | Evidência | Descrição da avaliação
        gap_table = doc.add_table(rows=len(resumo_gaps) + 1, cols=4)
        gap_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(gap_table, color=BORDER_HEX)

        # Header
        gap_headers = ["Área / Processo", "Gaps", "Evidência", "Descrição da avaliação"]
        col_widths = [1.8, 1.4, 2.2, 2.0]

        for c_idx, h_text in enumerate(gap_headers):
            c = gap_table.cell(0, c_idx)
            set_cell_background(c, NAVY_HEX)
            set_cell_margins(c, top=80, bottom=80, left=100, right=100)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(h_text)
            r.bold = True
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, item_gap in enumerate(resumo_gaps, 1):
            c_area = gap_table.cell(r_idx, 0)
            c_gaps = gap_table.cell(r_idx, 1)
            c_evid = gap_table.cell(r_idx, 2)
            c_desc = gap_table.cell(r_idx, 3)

            bg_row = LIGHT_BG_HEX if r_idx % 2 == 0 else "FFFFFF"
            for c in [c_area, c_gaps, c_evid, c_desc]:
                set_cell_margins(c, top=70, bottom=70, left=90, right=90)
                set_cell_background(c, bg_row)

            # 1. Área / Processo
            p_a = c_area.paragraphs[0]
            p_a.paragraph_format.space_after = Pt(0)
            r_a = p_a.add_run(item_gap['area'])
            r_a.bold = True
            r_a.font.size = Pt(8.5)

            # 2. Gaps
            p_g = c_gaps.paragraphs[0]
            p_g.paragraph_format.space_after = Pt(0)
            r_g = p_g.add_run(item_gap['gaps'])
            r_g.bold = True
            r_g.font.size = Pt(8.5)
            if item_gap['tipo'] == 'NC':
                r_g.font.color.rgb = RGBColor(220, 38, 38)
            else:
                r_g.font.color.rgb = RGBColor(217, 119, 6)

            # 3. Evidência
            p_e = c_evid.paragraphs[0]
            p_e.paragraph_format.space_after = Pt(0)
            r_e = p_e.add_run(item_gap['evidencia'])
            r_e.font.size = Pt(8.5)

            # 4. Descrição da avaliação
            p_d = c_desc.paragraphs[0]
            p_d.paragraph_format.space_after = Pt(0)
            r_d = p_d.add_run(item_gap['descricao'])
            r_d.font.size = Pt(8.5)
    else:
        p_vazio = doc.add_paragraph()
        p_vazio.paragraph_format.space_before = Pt(4)
        p_vazio.paragraph_format.space_after = Pt(6)
        r_vz = p_vazio.add_run("✅ Não foram identificadas Não Conformidades ou Gaps críticos durante esta auditoria. Todos os processos auditados demonstraram atendimento aos requisitos da norma.")
        r_vz.font.italic = True
        r_vz.font.size = Pt(9.5)
        r_vz.font.color.rgb = RGBColor(22, 101, 52)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # =========================================================================
    # 6. CONCLUSÃO E ASSINATURAS
    # =========================================================================
    sec4_title = doc.add_paragraph()
    sec4_title.paragraph_format.space_before = Pt(8)
    sec4_title.paragraph_format.space_after = Pt(4)
    r_sec4 = sec4_title.add_run("4. CONSIDERAÇÕES FINAIS E ASSINATURAS")
    r_sec4.bold = True
    r_sec4.font.size = Pt(12)
    r_sec4.font.color.rgb = RGBColor(11, 37, 69)

    conclusao_custom = getattr(auditoria, 'conclusao_texto', '') or ""
    if conclusao_custom:
        p_concl = doc.add_paragraph()
        p_concl.paragraph_format.space_after = Pt(8)
        r_c = p_concl.add_run(conclusao_custom)
        r_c.font.size = Pt(9.5)
    else:
        p_concl = doc.add_paragraph()
        p_concl.paragraph_format.space_after = Pt(8)
        r_c = p_concl.add_run(
            "A auditoria foi realizada com base em plano formal e amostragens representativas dos processos. "
            "Os resultados aqui expressos refletem a conformidade das operações em relação aos requisitos da norma e diretrizes da organização. "
            "Recomenda-se o acompanhamento dos prazos de implementação dos planos de ação para as oportunidades identificadas."
        )
        r_c.font.size = Pt(9.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    # Linhas de Assinatura
    sign_table = doc.add_table(rows=2, cols=2)
    sign_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    c_s0 = sign_table.cell(0, 0)
    c_s1 = sign_table.cell(0, 1)
    c_l0 = sign_table.cell(1, 0)
    c_l1 = sign_table.cell(1, 1)

    for cell in [c_s0, c_s1, c_l0, c_l1]:
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    c_s0.paragraphs[0].add_run("_________________________________________\n").font.size = Pt(9)
    c_s1.paragraphs[0].add_run("_________________________________________\n").font.size = Pt(9)

    r_aud = c_l0.paragraphs[0].add_run(f"Auditor Líder: {auditores_str}\nEquipe Auditora")
    r_aud.font.size = Pt(9)
    r_aud.bold = True

    r_rep = c_l1.paragraphs[0].add_run(f"Representante da Direção: {rep_str}\nUnidade Auditada")
    r_rep.font.size = Pt(9)
    r_rep.bold = True

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
