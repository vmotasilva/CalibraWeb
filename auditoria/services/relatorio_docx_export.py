import os
import io
import re
import base64
from typing import Optional, List, Dict, Any, Tuple
try:
    from django.conf import settings
except ImportError:
    settings = None
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
from bs4 import BeautifulSoup
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


def natural_sort_key(s: str):
    """Ordenação natural para referências como 4.1, 4.1.1, 4.10, etc."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s or ""))]


def set_cell_background(cell, color_hex: str):
    """Aplica cor de fundo a uma célula de tabela docx via XML."""
    color_hex = color_hex.replace("#", "").upper()
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
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


def ensure_master_template_docx_exists() -> str:
    """
    Cria ou atualiza o arquivo físico de template .docx no servidor com o padrão
    EssilorLuxottica (GQS-POL-017), fontes, tabelas com tags e seções corporativas.
    """
    template_path = get_template_docx_path()
    if os.path.exists(template_path) and os.path.getsize(template_path) > 1000:
        return template_path

    doc = Document()
    for s in doc.sections:
        s.page_height = Inches(11.69)
        s.page_width = Inches(8.27)
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.9)
        s.right_margin = Inches(0.9)

    # 1. Header Banner
    h_table = doc.add_table(rows=1, cols=1)
    h_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_h = h_table.cell(0, 0)
    set_cell_background(c_h, "0B2545")
    set_cell_margins(c_h, top=140, bottom=140, left=180, right=180)
    
    p_top = c_h.paragraphs[0]
    p_top.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_top = p_top.add_run("RELATÓRIO DE AUDITORIA INTERNA DA QUALIDADE")
    r_top.bold = True
    r_top.font.size = Pt(14)
    r_top.font.color.rgb = RGBColor(255, 255, 255)

    p_sub = c_h.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("Diretriz Corporativa GQS-POL-017 | {{norma_codigo}} — {{norma_descricao}}")
    r_sub.font.size = Pt(9.5)
    r_sub.font.color.rgb = RGBColor(226, 232, 240)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 2. Metadata Table
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(meta_table, color="CBD5E1")
    meta_rows = [
        ("Unidade / Empresa:", "{{unidade}}", "Data da Auditoria:", "{{data_auditoria}}"),
        ("Auditor(es) Líder(es):", "{{auditores}}", "Representantes Auditados:", "{{representantes}}"),
        ("Escopo da Auditoria:", "{{escopo}}", "Modalidade:", "{{modalidade}}"),
        ("Status do Ciclo:", "{{status}}", "Data do Relatório:", "{{data_relatorio}}"),
    ]
    for r_idx, (k1, v1, k2, v2) in enumerate(meta_rows):
        c0 = meta_table.cell(r_idx, 0)
        c1 = meta_table.cell(r_idx, 1)
        set_cell_margins(c0, top=60, bottom=60, left=100, right=100)
        set_cell_margins(c1, top=60, bottom=60, left=100, right=100)
        set_cell_background(c0, "F8FAFC" if r_idx % 2 == 0 else "FFFFFF")
        set_cell_background(c1, "F8FAFC" if r_idx % 2 == 0 else "FFFFFF")

        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        p0.add_run(f"{k1} ").bold = True
        p0.add_run(v1)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        p1.add_run(f"{k2} ").bold = True
        p1.add_run(v2)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 3. Section 1: Avaliação Geral
    p1 = doc.add_paragraph()
    p1.paragraph_format.space_before = Pt(8)
    p1.paragraph_format.space_after = Pt(4)
    r1 = p1.add_run("1. AVALIAÇÃO GERAL E RESULTADOS DA AUDITORIA")
    r1.bold = True
    r1.font.size = Pt(11.5)
    r1.font.color.rgb = RGBColor(11, 37, 69)

    res_table = doc.add_table(rows=8, cols=4)
    res_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(res_table, color="CBD5E1")
    
    table_data = [
        ("Classificação", "Sigla", "Qtd", "% Base"),
        ("Conforme", "C", "{{total_c}}", "{{pct_c}}%"),
        ("Não Conformidade Menor", "NC Menor", "{{total_nc_menor}}", "{{pct_nc_menor}}%"),
        ("Não Conformidade Maior", "NC Maior", "{{total_nc_maior}}", "{{pct_nc_maior}}%"),
        ("Oportunidade de Melhoria", "OM", "{{total_om}}", "{{pct_om}}%"),
        ("Observação / Correção Imediata", "OBS", "{{total_obs}}", "{{pct_obs}}%"),
        ("Não Aplicável (fora do escopo)", "NA", "{{total_na}}", "-"),
        ("Total de Requisitos / Amostras Avaliadas", "TOTAL", "{{total_avaliados}}", "100.0%"),
    ]
    for r_idx, (l0, l1, l2, l3) in enumerate(table_data):
        for c_idx, val in enumerate([l0, l1, l2, l3]):
            cell = res_table.cell(r_idx, c_idx)
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            if r_idx == 0:
                set_cell_background(cell, "0B2545")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(val)
                r.bold = True
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)
            else:
                if c_idx in [1, 2, 3]:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(val)
                r.font.size = Pt(9)
                if r_idx == 7 or c_idx == 1:
                    r.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Card Índice & Veredito
    card_t = doc.add_table(rows=1, cols=2)
    card_t.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(card_t, color="16A34A")
    c_s = card_t.cell(0, 0)
    set_cell_background(c_s, "DCFCE7")
    set_cell_margins(c_s, top=80, bottom=80, left=120, right=120)
    p_cs = c_s.paragraphs[0]
    p_cs.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cs.add_run("ÍNDICE GERAL DE CONFORMIDADE\n").bold = True
    p_cs.add_run("{{pct_conformidade}}%\n").bold = True

    c_v = card_t.cell(0, 1)
    set_cell_background(c_v, "F8FAFC")
    set_cell_margins(c_v, top=80, bottom=80, left=120, right=120)
    p_cv = c_v.paragraphs[0]
    p_cv.add_run("PARECER / VEREDITO DA AUDITORIA:\n").bold = True
    p_cv.add_run("{{veredito_status}}\n").bold = True
    p_cv.add_run("{{veredito_parecer}}")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 4. Section 2: Exclusões Justificadas
    p2 = doc.add_paragraph()
    p2.paragraph_format.space_before = Pt(8)
    p2.paragraph_format.space_after = Pt(4)
    r2 = p2.add_run("2. EXCLUSÕES DE REQUISITOS NORMATIVOS (JUSTIFICADAS)")
    r2.bold = True
    r2.font.size = Pt(11.5)
    r2.font.color.rgb = RGBColor(11, 37, 69)

    doc.add_paragraph("{{exclusoes_justificadas}}")
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 5. Section 3: Síntese da Auditoria
    p3 = doc.add_paragraph()
    p3.paragraph_format.space_before = Pt(8)
    p3.paragraph_format.space_after = Pt(4)
    r3 = p3.add_run("3. SÍNTESE EXECUTIVA DA AUDITORIA & NOTAS POR ÁREA FUNCIONAL")
    r3.bold = True
    r3.font.size = Pt(11.5)
    r3.font.color.rgb = RGBColor(11, 37, 69)

    doc.add_paragraph("{{sintese_narrativa}}")
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 6. Section 4: Resumo por Área Funcional (Tabela 4 Colunas)
    p4 = doc.add_paragraph()
    p4.paragraph_format.space_before = Pt(8)
    p4.paragraph_format.space_after = Pt(4)
    r4 = p4.add_run("4. RESUMO DA AUDITORIA POR ÁREA FUNCIONAL (GAPS & OPORTUNIDADES)")
    r4.bold = True
    r4.font.size = Pt(11.5)
    r4.font.color.rgb = RGBColor(11, 37, 69)

    gaps_table = doc.add_table(rows=2, cols=4)
    gaps_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(gaps_table, color="CBD5E1")
    
    gap_headers = ["Área / Processo", "Gaps", "Evidência", "Descrição"]
    for c_idx, h_text in enumerate(gap_headers):
        c = gaps_table.cell(0, c_idx)
        set_cell_background(c, "0B2545")
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(h_text)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(255, 255, 255)

    # Linha modelo com tags de repetição
    c0 = gaps_table.cell(1, 0); c0.paragraphs[0].add_run("{{gaps.area}}")
    c1 = gaps_table.cell(1, 1); c1.paragraphs[0].add_run("{{gaps.tipo_badge}}")
    c2 = gaps_table.cell(1, 2); c2.paragraphs[0].add_run("{{gaps.evidencia}}")
    c3 = gaps_table.cell(1, 3); c3.paragraphs[0].add_run("{{gaps.descricao}}")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 7. Section 5: Assinaturas
    p5 = doc.add_paragraph()
    p5.paragraph_format.space_before = Pt(8)
    p5.paragraph_format.space_after = Pt(4)
    r5 = p5.add_run("5. CONSIDERAÇÕES FINAIS E ASSINATURAS")
    r5.bold = True
    r5.font.size = Pt(11.5)
    r5.font.color.rgb = RGBColor(11, 37, 69)

    doc.add_paragraph("{{conclusao_texto}}")

    sign_table = doc.add_table(rows=2, cols=2)
    sign_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_s0 = sign_table.cell(0, 0); c_s1 = sign_table.cell(0, 1)
    c_l0 = sign_table.cell(1, 0); c_l1 = sign_table.cell(1, 1)
    for c in [c_s0, c_s1, c_l0, c_l1]:
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c_s0.paragraphs[0].add_run("_________________________________________\n").font.size = Pt(9)
    c_s1.paragraphs[0].add_run("_________________________________________\n").font.size = Pt(9)
    c_l0.paragraphs[0].add_run("Auditor Líder: {{auditores}}\nEquipe Auditora").bold = True
    c_l1.paragraphs[0].add_run("Representante da Direção: {{representantes}}\nUnidade Auditada").bold = True

    try:
        doc.save(template_path)
    except Exception:
        pass

    return template_path


def compute_auditoria_metricas_completas(auditoria) -> Dict[str, Any]:
    """
    Calcula com precisão matemática todos os contadores da auditoria ISO,
    utilizando a mesma lógica exata e consolidada do Dashboard de Fechamento.
    Corrige qualquer discrepância de contadores zerados.
    """
    try:
        from ..models import (
            ItemNorma,
            RespostaEntrevistaIso,
            AvaliacaoFinalRequisitoIso,
        )
    except Exception:
        ItemNorma = None
        RespostaEntrevistaIso = None
        AvaliacaoFinalRequisitoIso = None

    agendas_qs = auditoria.agendas.all() if hasattr(auditoria, 'agendas') else []
    if hasattr(agendas_qs, 'prefetch_related'):
        agendas_qs = agendas_qs.prefetch_related('perguntas', 'itens_norma', 'perguntas__itens_norma')
    agendas = list(agendas_qs)

    # Coleta de Itens do Escopo (com fallback completo)
    itens_escopo = auditoria.escopo_itens.all() if hasattr(auditoria, 'escopo_itens') else []
    if hasattr(itens_escopo, 'exists') and not itens_escopo.exists():
        if ItemNorma:
            itens_escopo = ItemNorma.objects.filter(norma=auditoria.norma)
    itens_escopo_list = list(itens_escopo)

    # Identifica itens pais que possuem subitens (avaliamos apenas folhas para não duplicar contagem)
    parent_ids = set()
    for item in itens_escopo_list:
        prefix = item.referencia + '.'
        if any(other.referencia.startswith(prefix) for other in itens_escopo_list):
            parent_ids.add(item.id)

    if RespostaEntrevistaIso:
        respostas = RespostaEntrevistaIso.objects.filter(auditoria=auditoria).prefetch_related(
            'solicitacoes', 'solicitacoes__imagens', 'pergunta__itens_norma'
        )
    else:
        respostas = []
    respostas_map = {r.pergunta_id: r for r in respostas}
    na_item_ids = set(auditoria.itens_nao_aplicaveis.values_list('id', flat=True)) if hasattr(auditoria, 'itens_nao_aplicaveis') else set()

    if AvaliacaoFinalRequisitoIso:
        avaliacoes_finais_map = {
            av.item_norma_id: av
            for av in AvaliacaoFinalRequisitoIso.objects.filter(auditoria=auditoria)
        }
    else:
        avaliacoes_finais_map = {}

    hierarchy = {"NC": 5, "P": 4, "OM": 3, "C": 2, "NA": 1}
    reverse_hierarchy = {v: k for k, v in hierarchy.items()}

    destaques_conformes = []
    pontos_a_melhorar = []
    exclusoes_na = []
    gaps_area_funcional = []

    count_c = 0
    count_obs = 0
    count_om = 0
    count_nc_menor = 0
    count_nc_maior = 0
    count_p = 0
    count_na = 0

    for item in sorted(itens_escopo_list, key=lambda x: (x.ordem or 0, natural_sort_key(x.referencia))):
        if item.id in parent_ids:
            continue

        todas_perguntas_dict = {}
        for ag in agendas:
            for p in ag.perguntas.all():
                if item in p.itens_norma.all() or (not p.itens_norma.exists() and item in ag.itens_norma.all()):
                    todas_perguntas_dict[p.id] = p
        todas_perguntas_item = list(todas_perguntas_dict.values())

        av_final = avaliacoes_finais_map.get(item.id)

        if av_final and av_final.classificacao:
            status_item = av_final.classificacao
        elif item.id in na_item_ids:
            status_item = "NA"
        elif not todas_perguntas_item:
            status_item = "P" if any(item in ag.itens_norma.all() for ag in agendas) else "NA"
        else:
            pior_peso = 0
            for p in todas_perguntas_item:
                r = respostas_map.get(p.id)
                c = r.classificacao if r else "P"
                if c == "OBS":
                    c = "C"
                peso = hierarchy.get(c, 2)
                if peso > pior_peso:
                    pior_peso = peso
            status_item = reverse_hierarchy.get(pior_peso, "P")

        # Evidências e Amostras do Requisito
        evidencias_item = []
        evidencias_vistas = set()
        sols_do_item = []

        for p in todas_perguntas_item:
            r = respostas_map.get(p.id)
            if r:
                sols_list = list(r.solicitacoes.all())
                sols_do_item.extend(sols_list)
                for s in sols_list:
                    if s.conclusao == 'OBS':
                        count_obs += 1
                    
                    ev_txt = ""
                    if s.evidencia and s.evidencia.strip():
                        if s.solicitacao and s.solicitacao.strip():
                            ev_txt = f"{s.solicitacao.strip()}: {s.evidencia.strip()}"
                        else:
                            ev_txt = s.evidencia.strip()
                    elif s.solicitacao and s.solicitacao.strip():
                        ev_txt = s.solicitacao.strip()

                    if ev_txt and ev_txt not in evidencias_vistas:
                        evidencias_vistas.add(ev_txt)
                        evidencias_item.append(ev_txt)

                if r.texto_resposta and r.texto_resposta.strip():
                    txt = r.texto_resposta.strip()
                    if txt not in evidencias_vistas:
                        evidencias_vistas.add(txt)
                        evidencias_item.append(txt)

        if av_final and av_final.justificativa and av_final.justificativa.strip():
            just_txt = f"Revisão: {av_final.justificativa.strip()}"
            if just_txt not in evidencias_vistas:
                evidencias_item.insert(0, just_txt)

        # Classificação do Requisito
        if status_item == 'NA':
            count_na += 1
            just_na = ""
            if av_final and av_final.justificativa:
                just_na = av_final.justificativa.strip()
            elif evidencias_item:
                just_na = " | ".join(evidencias_item)
            else:
                just_na = "Requisito declarado e avaliado como Não Aplicável (NA) ao escopo de atividades e produtos desta unidade."
            
            exclusoes_na.append({
                'referencia': item.referencia,
                'titulo': item.titulo,
                'justificativa': just_na
            })

        elif status_item == 'P':
            count_p += 1

        elif status_item == 'C':
            count_c += 1
            destaques_conformes.append({
                'referencia': item.referencia,
                'titulo': item.titulo,
                'evidencias': evidencias_item[:3] or ["Processo auditado com evidências documentais em conformidade."]
            })

        elif status_item == 'OM':
            count_om += 1
            ref_parts = item.referencia.split('.')
            sec_code = ref_parts[0] if ref_parts else item.referencia
            pai = ItemNorma.objects.filter(norma=auditoria.norma, referencia=sec_code).first() if ItemNorma else None
            area_nome = f"Seção {sec_code} - {pai.titulo if pai else item.titulo}"

            ev_str = "\n".join([f"• {e}" for e in evidencias_item]) if evidencias_item else "Amostragem realizada durante a auditoria."
            desc_str = av_final.justificativa if (av_final and av_final.justificativa) else f"Oportunidade de aprimoramento no cumprimento do requisito {item.referencia}."

            gaps_area_funcional.append({
                'area': area_nome,
                'item_referencia': item.referencia,
                'item_titulo': item.titulo,
                'tipo': 'OM',
                'tipo_badge': f"Oportunidade (Item {item.referencia})",
                'evidencia': ev_str,
                'descricao': desc_str
            })

        elif status_item == 'NC':
            if av_final and av_final.grau_nc:
                is_maior = (av_final.grau_nc == 'MAIOR')
            else:
                graus_definidos = []
                for p in todas_perguntas_item:
                    r = respostas_map.get(p.id)
                    if r and r.grau_nc:
                        graus_definidos.append(r.grau_nc)
                    if r:
                        for s in r.solicitacoes.all():
                            if s.conclusao == 'NC' and s.grau_nc:
                                graus_definidos.append(s.grau_nc)
                if graus_definidos:
                    is_maior = any(g == 'MAIOR' for g in graus_definidos)
                else:
                    is_maior = any('crítica' in ev.lower() or 'grave' in ev.lower() or 'sistêmica' in ev.lower() for ev in evidencias_item)

            if is_maior:
                count_nc_maior += 1
                tipo_nc = 'NC_MAIOR'
                badge_nc = f"NC Maior (Item {item.referencia})"
            else:
                count_nc_menor += 1
                tipo_nc = 'NC_MENOR'
                badge_nc = f"NC Menor (Item {item.referencia})"

            ref_parts = item.referencia.split('.')
            sec_code = ref_parts[0] if ref_parts else item.referencia
            pai = ItemNorma.objects.filter(norma=auditoria.norma, referencia=sec_code).first() if ItemNorma else None
            area_nome = f"Seção {sec_code} - {pai.titulo if pai else item.titulo}"

            ev_str = "\n".join([f"• {e}" for e in evidencias_item]) if evidencias_item else "Evidência constatada durante amostragem documental e entrevista."
            desc_str = av_final.justificativa if (av_final and av_final.justificativa) else f"Desvio identificado em relação aos critérios do requisito {item.referencia} da norma {auditoria.norma.codigo}."

            gaps_area_funcional.append({
                'area': area_nome,
                'item_referencia': item.referencia,
                'item_titulo': item.titulo,
                'tipo': 'NC',
                'tipo_badge': badge_nc,
                'evidencia': ev_str,
                'descricao': desc_str
            })

    total_avaliados = count_c + count_om + count_nc_menor + count_nc_maior
    total_base_calc = total_avaliados if total_avaliados > 0 else (count_c + count_na or 1)
    percentual_conformidade = round((count_c / total_avaliados * 100), 1) if total_avaliados > 0 else (100.0 if count_c > 0 else 0.0)

    # Veredito da Auditoria
    try:
        regras = {r.status_resultado: r for r in auditoria.norma.regras_veredicto.all()}
    except Exception:
        regras = {}

    regra_apto = regras.get('APTO')
    regra_ressalva = regras.get('RESSALVA')
    regra_inapto = regras.get('INAPTO')

    gatilho_nc_maior_inapto = regra_inapto.max_nc_maior if (regra_inapto and regra_inapto.max_nc_maior is not None) else 4
    gatilho_nc_menor_inapto = regra_inapto.max_nc_menor if (regra_inapto and regra_inapto.max_nc_menor is not None) else 15
    limite_nc_maior_apto = regra_apto.max_nc_maior if (regra_apto and regra_apto.max_nc_maior is not None) else 0
    limite_nc_menor_apto = regra_apto.max_nc_menor if (regra_apto and regra_apto.max_nc_menor is not None) else 2

    if count_nc_maior >= gatilho_nc_maior_inapto or count_nc_menor >= gatilho_nc_menor_inapto:
        veredito_status = "INADEQUADO / NÃO CONFORME"
        veredito_cor = "DC2626"
        veredito_bg = "FEE2E2"
        veredito_parecer = regra_inapto.texto_parecer_padrao if (regra_inapto and regra_inapto.texto_parecer_padrao) else (
            "Sistema inadequado e com alto risco crítico. As evidências apontam falhas sistêmicas que inviabilizam a recomendação neste ciclo. Recomenda-se plano de ação imediato e nova auditoria."
        )
    elif count_nc_maior <= limite_nc_maior_apto and count_nc_menor <= limite_nc_menor_apto:
        veredito_status = "ADEQUADO / CONFORME"
        veredito_cor = "16A34A"
        veredito_bg = "DCFCE7"
        veredito_parecer = regra_apto.texto_parecer_padrao if (regra_apto and regra_apto.texto_parecer_padrao) else (
            "O Sistema de Gestão da Qualidade atende satisfatoriamente aos requisitos normativos e demonstra maturidade operacional para a manutenção da certificação."
        )
    else:
        veredito_status = "MELHORIA NECESSÁRIA / RESSALVA"
        veredito_cor = "D97706"
        veredito_bg = "FEF9C3"
        veredito_parecer = regra_ressalva.texto_parecer_padrao if (regra_ressalva and regra_ressalva.texto_parecer_padrao) else (
            "O Sistema de Gestão da Qualidade requer a elaboração e cumprimento de Planos de Ação Corretiva formais para os desvios pontuais identificados, sem inviabilizar a recomendação geral."
        )

    gaps_area_funcional.sort(key=lambda x: natural_sort_key(x['item_referencia']))
    exclusoes_na.sort(key=lambda x: natural_sort_key(x['referencia']))

    return {
        'total_c': count_c,
        'pct_c': f"{(count_c/total_base_calc*100):.1f}" if total_base_calc else "0.0",
        'total_nc_menor': count_nc_menor,
        'pct_nc_menor': f"{(count_nc_menor/total_base_calc*100):.1f}" if total_base_calc else "0.0",
        'total_nc_maior': count_nc_maior,
        'pct_nc_maior': f"{(count_nc_maior/total_base_calc*100):.1f}" if total_base_calc else "0.0",
        'total_nc': count_nc_menor + count_nc_maior,
        'pct_nc': f"{((count_nc_menor + count_nc_maior)/total_base_calc*100):.1f}" if total_base_calc else "0.0",
        'total_om': count_om,
        'pct_om': f"{(count_om/total_base_calc*100):.1f}" if total_base_calc else "0.0",
        'total_obs': count_obs,
        'pct_obs': f"{(count_obs/total_base_calc*100):.1f}" if total_base_calc else "0.0",
        'total_na': count_na,
        'pct_na': "-",
        'total_p': count_p,
        'total_avaliados': total_avaliados,
        'pct_conformidade': percentual_conformidade,
        'veredito_status': veredito_status,
        'veredito_cor': veredito_cor,
        'veredito_bg': veredito_bg,
        'veredito_parecer': veredito_parecer,
        'destaques_conformes': destaques_conformes,
        'exclusoes_na': exclusoes_na,
        'gaps_area_funcional': gaps_area_funcional,
    }


def inject_html_to_docx(doc: Document, html_content: str, target_paragraph=None):
    """
    Converte código HTML (do editor WYSIWYG Quill/TinyMCE) nativamente em parágrafos,
    títulos, listas, tabelas e imagens no documento Word.
    """
    if not html_content or not html_content.strip():
        p = doc.add_paragraph() if target_paragraph is None else target_paragraph
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run("Nenhuma síntese ou nota registrada para este bloco.")
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
                r.font.size = Pt(9.0)
            elif child.name == 'img':
                src = child.get('src', '')
                if src:
                    insert_image_to_docx(doc, src, p)
            elif child.name == 'br':
                p.add_run('\n')
            else:
                process_inline(child, p)

    def insert_image_to_docx(doc_obj, src, target_p=None):
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
                
                max_w_px = 650
                if pil_img.width > max_w_px:
                    ratio = max_w_px / float(pil_img.width)
                    new_h = int(float(pil_img.height) * ratio)
                    pil_img = pil_img.resize((max_w_px, new_h), PILImage.Resampling.LANCZOS)

                img_io = io.BytesIO()
                pil_img.save(img_io, format='JPEG', quality=88)
                img_io.seek(0)

                img_p = target_p if target_p is not None else doc_obj.add_paragraph()
                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                img_p.paragraph_format.space_before = Pt(4)
                img_p.paragraph_format.space_after = Pt(6)
                img_p.add_run().add_picture(img_io, width=Inches(min(5.6, pil_img.width / 110.0)))
        except Exception:
            pass

    for elem in soup.find_all(recursive=False):
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(elem.name[1])
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.keep_with_next = True
            
            font_size = {1: 13, 2: 12, 3: 11, 4: 10, 5: 9.5, 6: 9.5}.get(level, 11)
            r = p.add_run(elem.get_text().strip())
            r.bold = True
            r.font.size = Pt(font_size)
            r.font.color.rgb = RGBColor(15, 23, 42)

        elif elem.name in ['p', 'div']:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(3)
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
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
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
                            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
                            p = cell.paragraphs[0]
                            p.paragraph_format.space_before = Pt(1)
                            p.paragraph_format.space_after = Pt(1)
                            process_inline(c_tag, p)
                            if is_header_row:
                                set_cell_background(cell, "F1F5F9")
                                for run in p.runs:
                                    run.bold = True
                                    run.font.size = Pt(9.0)
                            else:
                                for run in p.runs:
                                    run.font.size = Pt(8.5)

        elif elem.name == 'img':
            src = elem.get('src', '')
            if src:
                insert_image_to_docx(doc, src)


def replace_tags_in_paragraph(p, tag_dict: Dict[str, str]):
    """Substitui tags simples {{tag}} preservando a formatação do parágrafo."""
    full_text = p.text
    if "{{" not in full_text:
        return

    for tag, val in tag_dict.items():
        if tag in full_text:
            full_text = full_text.replace(tag, str(val))

    p.text = full_text


def replace_tags_in_document(doc: Document, tag_dict: Dict[str, str]):
    """Varre todos os parágrafos e tabelas do documento substituindo as tags."""
    for p in doc.paragraphs:
        replace_tags_in_paragraph(p, tag_dict)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_tags_in_paragraph(p, tag_dict)


def populate_gaps_table_loop(table, gaps_list: List[Dict[str, Any]]):
    """
    Executa o Table Row Looping na tabela de Gaps (4 colunas).
    Colunas: [ Área / Processo | Gaps | Evidência | Descrição ]
    """
    while len(table.rows) > 1:
        table._tbl.remove(table.rows[-1]._tr)

    NAVY_HEX = "0B2545"
    LIGHT_BG = "F8FAFC"
    WHITE = "FFFFFF"

    hdr_row = table.rows[0]
    headers = ["Área / Processo", "Gaps", "Evidência", "Descrição"]
    for c_idx, text in enumerate(headers):
        c = hdr_row.cells[c_idx]
        set_cell_background(c, NAVY_HEX)
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.text = ""
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(255, 255, 255)

    if not gaps_list:
        row = table.add_row()
        for cell in row.cells:
            set_cell_margins(cell, top=70, bottom=70, left=100, right=100)
            set_cell_background(cell, WHITE)
        
        a = row.cells[0]
        b = row.cells[3]
        a.merge(b)
        p = a.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("✅ Não foram identificadas Não Conformidades ou Gaps críticos durante esta auditoria. Todos os processos auditados demonstraram atendimento aos requisitos da norma.")
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(22, 101, 52)
        return

    for r_idx, gap in enumerate(gaps_list, 1):
        row = table.add_row()
        bg_color = LIGHT_BG if r_idx % 2 == 0 else WHITE

        for cell in row.cells:
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
            set_cell_background(cell, bg_color)

        # 0. Área / Processo
        p0 = row.cells[0].paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(gap.get('area', ''))
        r0.bold = True
        r0.font.size = Pt(8.5)
        r0.font.color.rgb = RGBColor(11, 37, 69)

        # 1. Gaps
        p1 = row.cells[1].paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(gap.get('tipo_badge', ''))
        r1.bold = True
        r1.font.size = Pt(8.5)
        if gap.get('tipo') == 'NC':
            r1.font.color.rgb = RGBColor(220, 38, 38)
        else:
            r1.font.color.rgb = RGBColor(217, 119, 6)

        # 2. Evidência
        p2 = row.cells[2].paragraphs[0]
        p2.paragraph_format.space_after = Pt(0)
        r2 = p2.add_run(gap.get('evidencia', ''))
        r2.font.size = Pt(8.5)

        # 3. Descrição
        p3 = row.cells[3].paragraphs[0]
        p3.paragraph_format.space_after = Pt(0)
        r3 = p3.add_run(gap.get('descricao', ''))
        r3.font.size = Pt(8.5)


def generate_relatorio_docx_buffer(auditoria) -> io.BytesIO:
    """
    Motor principal de exportação do Relatório de Auditoria Interna DOCX.
    Utiliza Template Engine com injeção de dados no arquivo .docx cadastrado na Norma,
    com fallback automático para o template mestre da aplicação, injeção de Exclusões Justificadas,
    Síntese Narrativa WYSIWYG e Table Row Looping para os Gaps da auditoria.
    """
    # 1. Obtém o template da norma ou template mestre
    norma = auditoria.norma
    doc = None

    if norma.template_docx and norma.template_docx.name:
        try:
            doc = Document(norma.template_docx.path)
        except Exception:
            try:
                norma.template_docx.open('rb')
                doc = Document(norma.template_docx.file)
            except Exception:
                doc = None

    if doc is None:
        template_path = ensure_master_template_docx_exists()
        if template_path and os.path.exists(template_path):
            doc = Document(template_path)
        else:
            raise ValueError("Nenhum template encontrado. Solicite ao administrador que faça o upload na aba Modelos (Uploads).")

    # 2. Extrai métricas consolidadas e listas de dados
    dados = compute_auditoria_metricas_completas(auditoria)

    # 3. Formata variáveis de cabeçalho e metadados
    unidade_str = getattr(auditoria, 'empresa_auditada', '') or "Unidade Auditada"
    auditores_list = [a.get_full_name() or a.username for a in auditoria.auditores.all()]
    auditores_str = ", ".join(auditores_list) if auditores_list else (auditoria.abertura_auditores or "Equipe Auditora Designada")
    
    dt_ini = auditoria.data_inicio.strftime('%d/%m/%Y') if auditoria.data_inicio else ""
    dt_fim = auditoria.data_fim.strftime('%d/%m/%Y') if auditoria.data_fim else ""
    datas_str = f"{dt_ini} a {dt_fim}" if (dt_ini and dt_fim and dt_ini != dt_fim) else (dt_ini or dt_fim or "Em andamento")
    rep_str = auditoria.encerramento_representantes or auditoria.abertura_representantes or "Representantes da Unidade Auditada"
    norma_desc = getattr(auditoria.norma, 'descricao', '') or ''
    escopo_str = getattr(auditoria, 'escopo', '') or (f"{auditoria.norma.codigo}" + (f" - {norma_desc}" if norma_desc else " - Sistema de Gestão da Qualidade"))

    conclusao_custom = getattr(auditoria, 'conclusao_texto', '') or ""
    if not conclusao_custom:
        conclusao_custom = (
            "A auditoria foi realizada com base em plano formal e amostragens representativas dos processos operacionais e de gestão. "
            "Os resultados expressos refletem a conformidade das operações em relação aos requisitos da norma e diretrizes da organização. "
            "Recomenda-se o acompanhamento dos prazos de implementação dos planos de ação para as oportunidades identificadas."
        )

    # Dicionário de Injeção de Tags (com sinônimos suportados)
    tag_dict = {
        '{{unidade}}': unidade_str,
        '{{nome_unidade}}': unidade_str,
        '{{empresa_auditada}}': unidade_str,
        '{{norma_codigo}}': auditoria.norma.codigo,
        '{{norma_descricao}}': norma_desc or "Sistema de Gestão da Qualidade",
        '{{escopo}}': escopo_str,
        '{{data_inicio}}': dt_ini,
        '{{data_fim}}': dt_fim,
        '{{data_auditoria}}': datas_str,
        '{{auditores}}': auditores_str,
        '{{nome_auditor}}': auditores_str,
        '{{auditor_lider}}': auditores_str,
        '{{equipe_auditora}}': auditores_str,
        '{{representantes}}': rep_str,
        '{{status}}': auditoria.get_status_display() if hasattr(auditoria, 'get_status_display') else "Concluída",
        '{{data_relatorio}}': dt_fim or dt_ini or "Hoje",
        '{{modalidade}}': "Presencial e Amostragem Documental",
        '{{total_c}}': str(dados['total_c']),
        '{{pct_c}}': str(dados['pct_c']),
        '{{total_nc_menor}}': str(dados['total_nc_menor']),
        '{{pct_nc_menor}}': str(dados['pct_nc_menor']),
        '{{total_nc_maior}}': str(dados['total_nc_maior']),
        '{{pct_nc_maior}}': str(dados['pct_nc_maior']),
        '{{total_nc}}': str(dados['total_nc']),
        '{{pct_nc}}': str(dados['pct_nc']),
        '{{total_om}}': str(dados['total_om']),
        '{{pct_om}}': str(dados['pct_om']),
        '{{total_obs}}': str(dados['total_obs']),
        '{{pct_obs}}': str(dados['pct_obs']),
        '{{total_na}}': str(dados['total_na']),
        '{{pct_na}}': str(dados['pct_na']),
        '{{total_avaliados}}': str(dados['total_avaliados']),
        '{{pct_conformidade}}': str(dados['pct_conformidade']),
        '{{taxa_conformidade}}': f"{dados['pct_conformidade']}%",
        '{{veredito_status}}': dados['veredito_status'],
        '{{veredito_parecer}}': dados['veredito_parecer'],
        '{{parecer_conclusao}}': dados['veredito_parecer'],
        '{{conclusao_parecer}}': dados['veredito_parecer'],
        '{{conclusao_texto}}': conclusao_custom,
    }

    # 4. Injeção de Tags Escalares no Documento
    replace_tags_in_document(doc, tag_dict)

    # 5. Injeção da Seção "Exclusões Justificadas"
    for p in doc.paragraphs:
        if "{{exclusoes_justificadas}}" in p.text:
            p.text = ""
            exclusoes = dados['exclusoes_na']
            if exclusoes:
                t_na = doc.add_table(rows=len(exclusoes) + 1, cols=3)
                t_na.alignment = WD_TABLE_ALIGNMENT.CENTER
                set_table_borders(t_na, color="CBD5E1")
                
                # Header
                for c_idx, h_t in enumerate(["Requisito", "Título do Item", "Justificativa da Não Aplicabilidade"]):
                    c = t_na.cell(0, c_idx)
                    set_cell_background(c, "0B2545")
                    set_cell_margins(c, top=70, bottom=70, left=90, right=90)
                    p_c = c.paragraphs[0]
                    p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = p_c.add_run(h_t)
                    r.bold = True
                    r.font.size = Pt(8.5)
                    r.font.color.rgb = RGBColor(255, 255, 255)

                for r_idx, item_na in enumerate(exclusoes, 1):
                    c0 = t_na.cell(r_idx, 0)
                    c1 = t_na.cell(r_idx, 1)
                    c2 = t_na.cell(r_idx, 2)
                    bg_row = "F8FAFC" if r_idx % 2 == 0 else "FFFFFF"
                    for c in [c0, c1, c2]:
                        set_cell_margins(c, top=60, bottom=60, left=80, right=80)
                        set_cell_background(c, bg_row)

                    c0.paragraphs[0].add_run(item_na['referencia']).bold = True
                    c0.paragraphs[0].runs[0].font.size = Pt(8.5)
                    c1.paragraphs[0].add_run(item_na['titulo']).font.size = Pt(8.5)
                    c2.paragraphs[0].add_run(item_na['justificativa']).font.size = Pt(8.5)

                p._p.addnext(t_na._tbl)
            else:
                p_na = doc.add_paragraph()
                p_na.paragraph_format.space_before = Pt(2)
                p_na.paragraph_format.space_after = Pt(4)
                r_na = p_na.add_run("Não foram identificadas exclusões de requisitos normativos no escopo desta auditoria. Todos os requisitos da norma foram considerados aplicáveis.")
                r_na.font.size = Pt(9.0)
                r_na.font.italic = True
                r_na.font.color.rgb = RGBColor(71, 85, 105)
                p._p.addnext(p_na._p)

    # 6. Injeção da Síntese Narrativa & Seções
    for p in doc.paragraphs:
        if "{{sintese_narrativa}}" in p.text:
            p.text = ""
            sinteses_secoes = list(auditoria.sinteses_secao.all())
            sinteses_secoes = sorted(sinteses_secoes, key=lambda s: natural_sort_key(s.secao_referencia))
            sintese_global_html = getattr(auditoria, 'sintese', '') or ""
            tem_sintese_secao = any(bool(s.conteudo_html and s.conteudo_html.strip()) for s in sinteses_secoes)

            if sintese_global_html and sintese_global_html.strip():
                inject_html_to_docx(doc, sintese_global_html)
                doc.add_paragraph().paragraph_format.space_after = Pt(4)

            if tem_sintese_secao:
                sec_num = 1
                for s in sinteses_secoes:
                    if s.conteudo_html and s.conteudo_html.strip():
                        p_shdr = doc.add_paragraph()
                        p_shdr.paragraph_format.space_before = Pt(8)
                        p_shdr.paragraph_format.space_after = Pt(2)
                        r_shdr = p_shdr.add_run(f"3.{sec_num} Seção {s.secao_referencia} — {s.secao_titulo}")
                        r_shdr.bold = True
                        r_shdr.font.size = Pt(10.0)
                        r_shdr.font.color.rgb = RGBColor(30, 58, 138)
                        
                        inject_html_to_docx(doc, s.conteudo_html)
                        doc.add_paragraph().paragraph_format.space_after = Pt(4)
                        sec_num += 1
            elif not (sintese_global_html and sintese_global_html.strip()):
                p_def = doc.add_paragraph()
                p_def.paragraph_format.space_after = Pt(4)
                r_def = p_def.add_run(
                    "A auditoria interna foi executada por amostragem abrangendo os processos críticos, "
                    "infraestrutura, controles operacionais e registros documentais da qualidade conforme escopo planejado."
                )
                r_def.font.size = Pt(9.0)
                r_def.font.italic = True
                r_def.font.color.rgb = RGBColor(71, 85, 105)

    # 7. Injeção na Tabela de Gaps (Table Row Looping - Tabela 4 Colunas)
    for table in doc.tables:
        if len(table.rows) > 0 and len(table.rows[0].cells) == 4:
            first_row_text = "".join([c.text for c in table.rows[0].cells])
            if "Área" in first_row_text and "Gaps" in first_row_text:
                populate_gaps_table_loop(table, dados['gaps_area_funcional'])

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
