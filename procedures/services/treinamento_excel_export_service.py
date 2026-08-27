# -*- coding: utf-8 -*-
"""
Serviço de Exportação de Formulários Oficiais em Excel (.xlsx)
Preenche automaticamente os templates:
1. FOR.133.r01 - Planejamento de Treinamento (Matriz relacional de cronograma)
2. FOR.141.r02 - Auto-Avaliação de Treinamento Crítico (5 perguntas)
3. FOR.142.r01 - Avaliação de Eficácia do Treinamento (Cálculo matemático de elegibilidade + 30 dias)
"""

import os
import base64
from io import BytesIO
from datetime import date, timedelta
from copy import copy
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.conf import settings
from django.utils import timezone
from procedures.models import (
    PlanejamentoTreinamento,
    RegistroTreinamento,
    TemplateDocumentoTreinamento,
    PerguntaAvaliacao
)


# ==============================================================================
# FUNÇÕES AUXILIARES DE MANIPULAÇÃO DE WORKBOOK E TAGS
# ==============================================================================

def _carregar_workbook_template(funcao: str, codigo_busca: str, nome_padrao: str):
    """
    Busca e carrega o arquivo openpyxl.Workbook a partir de:
    1. Template ativo no banco (Base64)
    2. Template ativo no banco (FileField)
    3. Sistema de arquivos local
    Retorna (wb, template_obj) ou (None, None).
    """
    template_config = TemplateDocumentoTreinamento.objects.filter(
        funcao=funcao,
        ativo=True
    ).first()

    if not template_config and codigo_busca:
        template_config = TemplateDocumentoTreinamento.objects.filter(
            codigo__icontains=codigo_busca,
            ativo=True
        ).first()

    wb = None

    if template_config:
        # A. Base64 gravado no banco de dados
        if getattr(template_config, 'arquivo_base64', None):
            try:
                arquivo_bytes = base64.b64decode(template_config.arquivo_base64)
                wb = openpyxl.load_workbook(BytesIO(arquivo_bytes))
            except Exception:
                wb = None

        # B. FileField
        if wb is None and template_config.arquivo:
            try:
                template_config.arquivo.seek(0)
                arquivo_bytes = BytesIO(template_config.arquivo.read())
                wb = openpyxl.load_workbook(arquivo_bytes)
            except Exception:
                wb = None

    # C. Fallback: Arquivos locais no projeto
    if wb is None and nome_padrao:
        caminhos = [
            os.path.join(settings.BASE_DIR, "templates", nome_padrao),
            os.path.join(settings.BASE_DIR, "procedures", "templates", nome_padrao),
            os.path.join(settings.BASE_DIR, "static", "templates", nome_padrao),
            os.path.join(settings.BASE_DIR, nome_padrao),
            os.path.join(settings.MEDIA_ROOT, "templates_treinamento_docs", nome_padrao),
        ]
        template_path = next((p for p in caminhos if os.path.exists(p)), None)
        if template_path:
            try:
                wb = openpyxl.load_workbook(template_path)
            except Exception:
                wb = None

    return wb, template_config


def _search_and_replace_sheet(sheet, mapping: dict):
    """
    Substitui todas as tags de texto nas células de uma planilha Excel.
    """
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                valor = str(cell.value)
                modificado = False
                for tag, novo_valor in mapping.items():
                    if tag in valor:
                        valor = valor.replace(tag, str(novo_valor if novo_valor is not None else ''))
                        modificado = True
                if modificado:
                    cell.value = valor


def _copiar_estilo_celula(origem, destino):
    """Copia fontes, bordas, preenchimento e alinhamento de uma célula para outra."""
    if origem.has_style:
        destino.font = copy(origem.font)
        destino.border = copy(origem.border)
        destino.fill = copy(origem.fill)
        destino.number_format = copy(origem.number_format)
        destino.protection = copy(origem.protection)
        destino.alignment = copy(origem.alignment)


# ==============================================================================
# 1. FOR.133.r01 - PLANEJAMENTO DE TREINAMENTO (MATRIZ DE CRONOGRAMA)
# ==============================================================================

def gerar_planejamento_matriz_for133_xlsx(planejamento: PlanejamentoTreinamento) -> BytesIO:
    """
    Gera a Matriz de Planejamento de Treinamento (FOR.133.r01).
    Eixos cruzados: Colaborador X Procedimento X Facilitador com Linha do Tempo (Jan-Dez).
    """
    wb, template_obj = _carregar_workbook_template(
        funcao='PLANEJAMENTO_MATRIZ',
        codigo_busca='133',
        nome_padrao='FOR.133.r01_Planejamento_de_Treinamento.xlsx'
    )

    data_ref = planejamento.data_prevista or planejamento.criado_em.date()
    ano_str = str(data_ref.year)
    instrutor_nome = planejamento.instrutor.nome_completo if planejamento.instrutor else "-"
    
    colaboradores = list(planejamento.colaboradores.select_related('setor').all())
    procedimentos = list(planejamento.procedimentos.all())
    setor_nome = colaboradores[0].setor.nome if (colaboradores and colaboradores[0].setor) else "-"

    mes_planejado = planejamento.data_prevista.month if planejamento.data_prevista else None
    mes_realizado = planejamento.data_realizada.month if planejamento.data_realizada else None

    substituicoes = {
        "{{ANO}}": ano_str,
        "{{TITULO}}": planejamento.titulo or "-",
        "{{INSTRUTOR}}": instrutor_nome,
        "{{FACILITADOR}}": instrutor_nome,
        "{{SETOR}}": setor_nome,
        "{{DEPARTAMENTO}}": setor_nome,
        "{{DATA_EMISSAO}}": timezone.now().strftime("%d/%m/%Y"),
        "{{CARGA_HORARIA}}": f"{planejamento.carga_horaria} Minutos" if planejamento.carga_horaria else "-",
        "{{STATUS}}": planejamento.get_status_display() if hasattr(planejamento, 'get_status_display') else planejamento.status,
    }

    # Se carregou um template existente
    if wb is not None:
        ws = wb.active
        for sheet in wb.worksheets:
            _search_and_replace_sheet(sheet, substituicoes)

        # Verificar se é o layout oficial do FOR.133 (Cabeçalho na linha 3)
        eh_layout_oficial_133 = False
        for r in range(1, 6):
            for c in range(1, 10):
                v = str(sheet.cell(r, c).value or '').upper()
                if "NOME DO FORMANDO" in v or "TITULO DO TREINAMENTO" in v or "TÍTULO DO TREINAMENTO" in v:
                    eh_layout_oficial_133 = True
                    break

        if eh_layout_oficial_133:
            # Preencher a partir da linha 4
            row_idx = 4
            for colab in (colaboradores or [None]):
                for proc in (procedimentos or [None]):
                    colab_nome = colab.nome_completo if colab else "A Definir"
                    proc_nome = f"{proc.codigo} - {proc.nome}" if proc else (planejamento.titulo or "-")
                    
                    ws.cell(row=row_idx, column=2, value=proc_nome) # Col B: Título
                    ws.cell(row=row_idx, column=3, value=instrutor_nome) # Col C: Formador
                    ws.cell(row=row_idx, column=4, value=colab_nome) # Col D: Formando
                    ws.cell(row=row_idx, column=5, value="Treinamento Técnico / Operacional") # Col E: Metodologia
                    
                    # Carga horária
                    ch_min = planejamento.carga_horaria or 60
                    ws.cell(row=row_idx, column=6, value=f"{ch_min//60:02d}:{ch_min%60:02d}") # Col F: hh:mm
                    ws.cell(row=row_idx, column=7, value=round(ch_min/60, 2)) # Col G: h
                    
                    # Colunas de Meses: H (Jan, col 8) a S (Dez, col 19)
                    for m in range(1, 13):
                        col_mes = 7 + m
                        if mes_realizado == m:
                            ws.cell(row=row_idx, column=col_mes, value="R")
                        elif mes_planejado == m:
                            ws.cell(row=row_idx, column=col_mes, value="P")
                    row_idx += 1
        else:
            # Localizar âncora da tabela de colaboradores/procedimentos
            anchor_row = None
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        v_up = cell.value.upper()
                        if "{{COLABORADOR}}" in v_up or "{{TABELA_MATRIZ}}" in v_up or "NOME DO COLABORADOR" in v_up:
                            anchor_row = cell.row
                            break
                if anchor_row:
                    break

            if anchor_row:
                linha_atual = anchor_row + 1 if "NOME DO COLABORADOR" in str(ws.cell(anchor_row, 1).value or '').upper() else anchor_row
                for colab in colaboradores:
                    for proc in (procedimentos or [None]):
                        ws.cell(row=linha_atual, column=1, value=colab.nome_completo)
                        ws.cell(row=linha_atual, column=2, value=colab.matricula or "-")
                        ws.cell(row=linha_atual, column=3, value=colab.cargo or "-")
                        ws.cell(row=linha_atual, column=4, value=f"{proc.codigo} - {proc.nome}" if proc else "-")
                        ws.cell(row=linha_atual, column=5, value=instrutor_nome)
                        
                        # Colunas de Meses (assumindo colunas 6 a 17 para Jan-Dez)
                        for m in range(1, 13):
                            col_mes = 5 + m
                            if col_mes <= ws.max_column:
                                if mes_realizado == m:
                                    ws.cell(row=linha_atual, column=col_mes, value="R")
                                elif mes_planejado == m:
                                    ws.cell(row=linha_atual, column=col_mes, value="P")
                        linha_atual += 1

    else:
        # Gerador nativo de alta fidelidade para FOR.133.r01
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cronograma FOR.133"

        # Estilos Oficiais
        font_header_doc = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        font_sub_doc = Font(name="Arial", size=9, bold=True, color="1E293B")
        font_th = Font(name="Arial", size=8.5, bold=True, color="FFFFFF")
        font_td = Font(name="Arial", size=8.5, color="000000")
        font_meta = Font(name="Arial", size=8.5, bold=True, color="334155")
        font_val = Font(name="Arial", size=8.5, color="0F172A")

        fill_header_doc = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        fill_meta = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_th = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        fill_meses_th = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        fill_planejado = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid") # Azul claro
        fill_realizado = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # Verde claro

        border_thin = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )

        align_center = Alignment(horizontal='center', vertical='center')
        align_left = Alignment(horizontal='left', vertical='center')

        # Cabeçalho do Formulário
        ws.merge_cells("A1:R1")
        cell_top = ws.cell(row=1, column=1, value="FOR.133.r01 - PLANEJAMENTO DE TREINAMENTO / CRONOGRAMA")
        cell_top.font = font_header_doc
        cell_top.fill = fill_header_doc
        cell_top.alignment = align_center
        ws.row_dimensions[1].height = 28

        # Metadados do Planejamento
        meta_rows = [
            ("Título do Treinamento:", planejamento.titulo or "-", "Ano de Referência:", ano_str),
            ("Instrutor / Facilitador:", instrutor_nome, "Setor / Departamento:", setor_nome),
            ("Carga Horária:", f"{planejamento.carga_horaria} Minutos" if planejamento.carga_horaria else "-", "Status do Planejamento:", planejamento.status),
        ]

        for idx, (lbl1, val1, lbl2, val2) in enumerate(meta_rows, start=2):
            ws.merge_cells(start_row=idx, start_column=2, end_row=idx, end_column=10)
            ws.merge_cells(start_row=idx, start_column=12, end_row=idx, end_column=18)

            c_lbl1 = ws.cell(row=idx, column=1, value=lbl1)
            c_val1 = ws.cell(row=idx, column=2, value=val1)
            c_lbl2 = ws.cell(row=idx, column=11, value=lbl2)
            c_val2 = ws.cell(row=idx, column=12, value=val2)

            for col in range(1, 19):
                c = ws.cell(row=idx, column=col)
                c.border = border_thin
                if col in [1, 11]:
                    c.font = font_meta
                    c.fill = fill_meta
                    c.alignment = align_left
                else:
                    c.font = font_val
                    c.alignment = align_left
            ws.row_dimensions[idx].height = 18

        # Linha em branco
        ws.row_dimensions[5].height = 6

        # Cabeçalho da Matriz Relacional
        headers_base = [
            "Nº", "Colaborador", "Matrícula", "Cargo / Função",
            "Procedimento (Código / Nome)", "Facilitador"
        ]
        meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

        for col_idx, h_text in enumerate(headers_base, start=1):
            c = ws.cell(row=6, column=col_idx, value=h_text)
            c.font = font_th
            c.fill = fill_th
            c.alignment = align_center
            c.border = border_thin

        for col_idx, m_text in enumerate(meses_nomes, start=7):
            c = ws.cell(row=6, column=col_idx, value=m_text)
            c.font = font_th
            c.fill = fill_meses_th
            c.alignment = align_center
            c.border = border_thin

        ws.row_dimensions[6].height = 22

        # Linhas de Dados (Cruzamento Colaborador X Procedimento)
        row_num = 7
        item_counter = 1

        lista_colabs = colaboradores if colaboradores else [None]
        lista_procs = procedimentos if procedimentos else [None]

        for colab in lista_colabs:
            for proc in lista_procs:
                colab_nome = colab.nome_completo if colab else "A Definir"
                colab_mat = colab.matricula if colab else "-"
                colab_cargo = colab.cargo if colab else "-"
                proc_str = f"{proc.codigo} - {proc.nome}" if proc else "Instruções Gerais de Treinamento"

                row_vals = [
                    item_counter,
                    colab_nome,
                    colab_mat,
                    colab_cargo,
                    proc_str,
                    instrutor_nome,
                ]

                for col_idx, val in enumerate(row_vals, start=1):
                    c = ws.cell(row=row_num, column=col_idx, value=val)
                    c.font = font_td
                    c.border = border_thin
                    c.alignment = align_center if col_idx in [1, 3] else align_left

                # Preenchimento das 12 colunas de meses
                for m_idx in range(1, 13):
                    col_m = 6 + m_idx
                    c_mes = ws.cell(row=row_num, column=col_m)
                    c_mes.border = border_thin
                    c_mes.alignment = align_center
                    c_mes.font = font_td

                    if mes_realizado == m_idx:
                        c_mes.value = "R"
                        c_mes.fill = fill_realizado
                        c_mes.font = Font(name="Arial", size=9, bold=True, color="166534")
                    elif mes_planejado == m_idx:
                        c_mes.value = "P"
                        c_mes.fill = fill_planejado
                        c_mes.font = Font(name="Arial", size=9, bold=True, color="1E40AF")
                    else:
                        c_mes.value = ""

                ws.row_dimensions[row_num].height = 19
                row_num += 1
                item_counter += 1

        # Legenda no Rodapé
        ws.row_dimensions[row_num].height = 8
        row_legenda = row_num + 1

        ws.cell(row=row_legenda, column=2, value="Legenda:")
        ws.cell(row=row_legenda, column=2).font = font_meta

        c_leg_p = ws.cell(row=row_legenda, column=3, value="P = Planejado")
        c_leg_p.fill = fill_planejado
        c_leg_p.font = Font(name="Arial", size=8.5, bold=True, color="1E40AF")
        c_leg_p.border = border_thin
        c_leg_p.alignment = align_center

        c_leg_r = ws.cell(row=row_legenda, column=4, value="R = Realizado")
        c_leg_r.fill = fill_realizado
        c_leg_r.font = Font(name="Arial", size=8.5, bold=True, color="166534")
        c_leg_r.border = border_thin
        c_leg_r.alignment = align_center

        # Ajuste de larguras das colunas
        larguras = {
            'A': 5, 'B': 28, 'C': 12, 'D': 20, 'E': 34, 'F': 24,
            'G': 6, 'H': 6, 'I': 6, 'J': 6, 'K': 6, 'L': 6,
            'M': 6, 'N': 6, 'O': 6, 'P': 6, 'Q': 6, 'R': 6
        }
        for col_letter, width in larguras.items():
            ws.column_dimensions[col_letter].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ==============================================================================
# 2. FOR.141.r02 - AUTO-AVALIAÇÃO DE TREINAMENTO CRÍTICO (5 PERGUNTAS)
# ==============================================================================

def _obter_perguntas_treinamento(planejamento: PlanejamentoTreinamento) -> list:
    """
    Recupera as 5 perguntas de autoavaliação para o treinamento crítico.
    Prioridade: Procedimento > Matriz > Perguntas Padrão SGQ.
    """
    procs = list(planejamento.procedimentos.all())
    perguntas = []

    # 1. Buscar por Procedimento
    if procs:
        proc_ids = [p.id for p in procs]
        perguntas = list(
            PerguntaAvaliacao.objects.filter(procedimento_id__in=proc_ids, ativo=True)
            .order_by('ordem')[:5]
        )

    # 2. Buscar por Matriz
    if len(perguntas) < 5 and procs:
        matrizes_nomes = [p.matriz for p in procs if p.matriz]
        if matrizes_nomes:
            perguntas_matriz = list(
                PerguntaAvaliacao.objects.filter(matriz__nome__in=matrizes_nomes, ativo=True)
                .order_by('ordem')[:5 - len(perguntas)]
            )
            perguntas.extend(perguntas_matriz)

    # 3. Fallback: 5 Perguntas Padrão Técnicas e de Qualidade
    perguntas_padrao = [
        "Qual o objetivo principal deste procedimento operacional e quais os impactos de eventuais não conformidades no processo?",
        "Quais os equipamentos de proteção individual (EPIs), ferramentas e requisitos de segurança obrigatórios para esta atividade?",
        "Descreva a sequência padrão de execução das etapas e os principais parâmetros operacionais a serem rigorosamente controlados.",
        "Quais são os pontos críticos de controle (PCC), tolerâncias permitidas e critérios de aceitação do produto/serviço?",
        "Em caso de desvio, defeito ou falha identificada durante a operação, qual é o fluxo correto de contenção e comunicação imediata?"
    ]

    perguntas_texto = [p.enunciado for p in perguntas]
    for p_padrao in perguntas_padrao:
        if len(perguntas_texto) >= 5:
            break
        if p_padrao not in perguntas_texto:
            perguntas_texto.append(p_padrao)

    return perguntas_texto[:5]


def gerar_auto_avaliacao_for141_xlsx(planejamento: PlanejamentoTreinamento, colaborador_id: int = None) -> BytesIO:
    """
    Gera o Formulário de Auto-Avaliação de Treinamento Crítico (FOR.141.r02).
    Injeta as 5 perguntas técnicas e dados do treinamento.
    """
    wb, template_obj = _carregar_workbook_template(
        funcao='AUTO_AVALIACAO',
        codigo_busca='141',
        nome_padrao='FOR.141.r02_Auto_Avaliacao.xlsx'
    )

    perguntas = _obter_perguntas_treinamento(planejamento)
    procs = list(planejamento.procedimentos.all())
    proc_str = ", ".join([f"{p.codigo} - {p.nome}" for p in procs]) if procs else (planejamento.titulo or "-")
    instrutor_nome = planejamento.instrutor.nome_completo if planejamento.instrutor else "-"
    data_str = planejamento.data_prevista.strftime("%d/%m/%Y") if planejamento.data_prevista else timezone.now().strftime("%d/%m/%Y")

    # Colaborador específico ou lista
    colaborador = None
    if colaborador_id:
        colaborador = planejamento.colaboradores.filter(id=colaborador_id).first()
    if not colaborador and planejamento.colaboradores.exists():
        colaborador = planejamento.colaboradores.first()

    colab_nome = colaborador.nome_completo if colaborador else "________________________________________"
    colab_mat = colaborador.matricula if colaborador else "_________"
    colab_cargo = colaborador.cargo if colaborador else "____________________"
    colab_setor = colaborador.setor.nome if (colaborador and colaborador.setor) else "____________________"

    substituicoes = {
        "{{TITULO}}": planejamento.titulo or "-",
        "{{PROCEDIMENTO}}": proc_str,
        "{{CODIGO_PROCEDIMENTO}}": procs[0].codigo if procs else "-",
        "{{NOME_PROCEDIMENTO}}": procs[0].nome if procs else (planejamento.titulo or "-"),
        "{{COLABORADOR}}": colab_nome,
        "{{NOME_COLABORADOR}}": colab_nome,
        "{{MATRICULA}}": colab_mat,
        "{{CARGO}}": colab_cargo,
        "{{SETOR}}": colab_setor,
        "{{DEPARTAMENTO}}": colab_setor,
        "{{INSTRUTOR}}": instrutor_nome,
        "{{FACILITADOR}}": instrutor_nome,
        "{{DATA}}": data_str,
        "{{DATA_HORA}}": data_str,
        "{{CARGA_HORARIA}}": f"{planejamento.carga_horaria} Minutos" if planejamento.carga_horaria else "-",
        "{{PER_1}}": perguntas[0] if len(perguntas) > 0 else "",
        "{{PER_2}}": perguntas[1] if len(perguntas) > 1 else "",
        "{{PER_3}}": perguntas[2] if len(perguntas) > 2 else "",
        "{{PER_4}}": perguntas[3] if len(perguntas) > 3 else "",
        "{{PER_5}}": perguntas[4] if len(perguntas) > 4 else "",
        "{{PERGUNTA_1}}": perguntas[0] if len(perguntas) > 0 else "",
        "{{PERGUNTA_2}}": perguntas[1] if len(perguntas) > 1 else "",
        "{{PERGUNTA_3}}": perguntas[2] if len(perguntas) > 2 else "",
        "{{PERGUNTA_4}}": perguntas[3] if len(perguntas) > 3 else "",
        "{{PERGUNTA_5}}": perguntas[4] if len(perguntas) > 4 else "",
    }

    if wb is not None:
        ws = wb.active
        for sheet in wb.worksheets:
            _search_and_replace_sheet(sheet, substituicoes)

        # Injeção no layout oficial FOR.141 se detectado (C2 / C10)
        eh_layout_141 = False
        for r in range(1, 5):
            for c in range(1, 6):
                v = str(ws.cell(r, c).value or '').upper()
                if "AUTO-AVALIA" in v or "AUTOAVALIA" in v:
                    eh_layout_141 = True
                    break

        if eh_layout_141:
            for r in range(2, 9):
                v_label = str(ws.cell(r, 3).value or '').strip().upper()
                if "NOME:" in v_label:
                    ws.cell(row=r, column=4, value=colab_nome)
                elif "LABORAT" in v_label or "SETOR" in v_label:
                    ws.cell(row=r, column=4, value=colab_setor)
                elif "TREINAMENTO:" in v_label:
                    ws.cell(row=r, column=4, value=proc_str)
                elif "DATA:" in v_label:
                    ws.cell(row=r, column=4, value=data_str)
                elif "INSTRUTOR:" in v_label:
                    ws.cell(row=r, column=4, value=instrutor_nome)

            # Injetar as 5 perguntas no questionário
            linhas_perguntas = [13, 16, 19, 22, 25]
            for p_idx, p_txt in enumerate(perguntas):
                if p_idx < len(linhas_perguntas):
                    r_p = linhas_perguntas[p_idx]
                    ws.cell(row=r_p, column=3, value=f"{p_idx+1}. {p_txt}")
    else:
        # Gerador nativo de alta fidelidade para FOR.141.r02
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Auto-Avaliação FOR.141"

        font_header_doc = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        font_section = Font(name="Arial", size=9.5, bold=True, color="FFFFFF")
        font_label = Font(name="Arial", size=8.5, bold=True, color="334155")
        font_val = Font(name="Arial", size=8.5, color="0F172A")
        font_pergunta = Font(name="Arial", size=9, bold=True, color="1E3A8A")

        fill_header_doc = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        fill_section = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        fill_meta = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_pergunta = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")

        border_box = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )

        align_center = Alignment(horizontal='center', vertical='center')
        align_left = Alignment(horizontal='left', vertical='center')
        align_top_left = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # 1. Cabeçalho Principal
        ws.merge_cells("A1:G1")
        c_top = ws.cell(row=1, column=1, value="FOR.141.r02 - AUTO-AVALIAÇÃO DE TREINAMENTO CRÍTICO")
        c_top.font = font_header_doc
        c_top.fill = fill_header_doc
        c_top.alignment = align_center
        ws.row_dimensions[1].height = 28

        # 2. Dados do Colaborador e Treinamento
        dados_header = [
            ("Colaborador:", colab_nome, "Matrícula:", colab_mat),
            ("Cargo / Função:", colab_cargo, "Setor:", colab_setor),
            ("Procedimento / Treinamento:", proc_str, "Data:", data_str),
            ("Instrutor / Facilitador:", instrutor_nome, "Carga Horária:", f"{planejamento.carga_horaria} Minutos" if planejamento.carga_horaria else "-"),
        ]

        for idx, (l1, v1, l2, v2) in enumerate(dados_header, start=2):
            ws.merge_cells(start_row=idx, start_column=2, end_row=idx, end_column=4)
            ws.merge_cells(start_row=idx, start_column=6, end_row=idx, end_column=7)

            ws.cell(row=idx, column=1, value=l1)
            ws.cell(row=idx, column=2, value=v1)
            ws.cell(row=idx, column=5, value=l2)
            ws.cell(row=idx, column=6, value=v2)

            for col in range(1, 8):
                c = ws.cell(row=idx, column=col)
                c.border = border_box
                if col in [1, 5]:
                    c.font = font_label
                    c.fill = fill_meta
                    c.alignment = align_left
                else:
                    c.font = font_val
                    c.alignment = align_left
            ws.row_dimensions[idx].height = 18

        ws.row_dimensions[6].height = 6

        # 3. Seção de Perguntas
        ws.merge_cells("A7:G7")
        c_sec = ws.cell(row=7, column=1, value="QUESTIONÁRIO DE AUTOAVALIAÇÃO TÉCNICA (5 PERGUNTAS OBRIGATÓRIAS)")
        c_sec.font = font_section
        c_sec.fill = fill_section
        c_sec.alignment = align_center
        ws.row_dimensions[7].height = 20

        current_row = 8
        for num_p, p_texto in enumerate(perguntas, start=1):
            # Linha da Pergunta
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
            c_p = ws.cell(row=current_row, column=1, value=f"Questão {num_p}: {p_texto}")
            c_p.font = font_pergunta
            c_p.fill = fill_pergunta
            c_p.alignment = align_left
            for col in range(1, 8):
                ws.cell(row=current_row, column=col).border = border_box
            ws.row_dimensions[current_row].height = 24
            current_row += 1

            # Espaço para resposta do colaborador (3 linhas mescladas)
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row + 2, end_column=7)
            c_resp = ws.cell(row=current_row, column=1, value="Resposta do Colaborador:\n\n")
            c_resp.font = Font(name="Arial", size=8, italic=True, color="64748B")
            c_resp.alignment = align_top_left
            for r_sub in range(current_row, current_row + 3):
                for col in range(1, 8):
                    ws.cell(row=r_sub, column=col).border = border_box
                ws.row_dimensions[r_sub].height = 16
            current_row += 3

        # 4. Bloco de Assinaturas
        ws.row_dimensions[current_row].height = 8
        current_row += 1

        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=3)
        ws.merge_cells(start_row=current_row, start_column=5, end_row=current_row, end_column=7)

        c_ass_colab = ws.cell(row=current_row, column=1, value="Assinatura do Colaborador")
        c_ass_colab.font = font_label
        c_ass_colab.alignment = align_center

        c_ass_inst = ws.cell(row=current_row, column=5, value="Assinatura do Instrutor / Avaliador")
        c_ass_inst.font = font_label
        c_ass_inst.alignment = align_center

        # Ajuste de larguras das colunas
        larguras_141 = {'A': 16, 'B': 24, 'C': 16, 'D': 16, 'E': 14, 'F': 22, 'G': 18}
        for col_letter, width in larguras_141.items():
            ws.column_dimensions[col_letter].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ==============================================================================
# 3. FOR.142.r01 - AVALIAÇÃO DE EFICÁCIA DO TREINAMENTO (+30 DIAS)
# ==============================================================================

def gerar_avaliacao_eficacia_for142_xlsx(treinamento_id: int) -> BytesIO:
    """
    Gera o Formulário de Avaliação de Eficácia do Treinamento (FOR.142.r01).
    Calcula a Data Devida da Eficácia (Data do Treinamento + 30 dias).
    """
    treinamento = RegistroTreinamento.objects.select_related(
        'colaborador', 'procedimento', 'colaborador__setor', 'colaborador__lider',
        'colaborador__supervisor', 'colaborador__gerente'
    ).get(id=treinamento_id)

    wb, template_obj = _carregar_workbook_template(
        funcao='AVALIACAO_EFICACIA',
        codigo_busca='142',
        nome_padrao='FOR.142.r01_Avaliacao_de_Eficacia_do_Treinamento.xlsx'
    )

    colab = treinamento.colaborador
    proc = treinamento.procedimento

    responsavel_nome = "-"
    if colab:
        if colab.posto_lideranca == 'SUPERVISOR':
            responsavel_nome = colab.gerente.nome_completo if colab.gerente else "-"
        elif colab.posto_lideranca == 'LIDER':
            responsavel_nome = colab.supervisor.nome_completo if colab.supervisor else "-"
        else:
            responsavel_nome = colab.lider.nome_completo if colab.lider else "-"

    data_treinamento = treinamento.data_treinamento or timezone.now().date()
    data_eficacia_calculada = data_treinamento + timedelta(days=30)
    data_treinamento_str = data_treinamento.strftime("%d/%m/%Y")
    data_eficacia_str = data_eficacia_calculada.strftime("%d/%m/%Y")
    data_avaliacao_str = treinamento.avaliacao_eficacia_data.strftime("%d/%m/%Y") if treinamento.avaliacao_eficacia_data else "-"

    status_str = treinamento.avaliacao_eficacia_status or "PENDENTE"
    status_map = {
        'EFICAZ': 'Eficaz',
        'INEFICAZ': 'Ineficaz',
        'NAO_APLICA': 'Não se Aplica',
        'PENDENTE': 'Pendente'
    }
    status_display = status_map.get(status_str, status_str)

    substituicoes = {
        "{{COLABORADOR}}": colab.nome_completo if colab else "-",
        "{{NOME_COLABORADOR}}": colab.nome_completo if colab else "-",
        "{{MATRICULA}}": colab.matricula if colab else "-",
        "{{CARGO}}": colab.cargo or "-" if colab else "-",
        "{{SETOR}}": colab.setor.nome if (colab and colab.setor) else "-",
        "{{DEPARTAMENTO}}": colab.setor.nome if (colab and colab.setor) else "-",
        "{{RESPONSAVEL}}": responsavel_nome,
        "{{LIDER}}": responsavel_nome,
        "{{AVALIADOR}}": responsavel_nome,
        "{{PROCEDIMENTO}}": f"{proc.codigo} - {proc.nome}" if proc else "-",
        "{{CODIGO_PROCEDIMENTO}}": proc.codigo if proc else "-",
        "{{NOME_PROCEDIMENTO}}": proc.nome if proc else "-",
        "{{DATA_TREINAMENTO}}": data_treinamento_str,
        "{{DATA_EFICACIA_CALCULADA}}": data_eficacia_str,
        "{{DATA_ELEGIBILIDADE}}": data_eficacia_str,
        "{{DATA_AVALIACAO}}": data_avaliacao_str,
        "{{STATUS_EFICACIA}}": status_display,
        "{{OBSERVACOES}}": treinamento.resultado_avaliacao or "",
        "{{JUSTIFICATIVA}}": treinamento.resultado_avaliacao or "",
        "{{EVIDENCIAS}}": treinamento.resultado_avaliacao or "",
        "{{CHK_EFICAZ}}": "●" if status_str == 'EFICAZ' else "○",
        "{{CHK_INEFICAZ}}": "●" if status_str == 'INEFICAZ' else "○",
        "{{CHK_NAO_APLICA}}": "●" if status_str == 'NAO_APLICA' else "○",
    }

    if wb is not None:
        ws = wb.active
        for sheet in wb.worksheets:
            _search_and_replace_sheet(sheet, substituicoes)

        # Injeção no layout oficial FOR.142 se detectado (B1 == AVALIAÇÃO DE EFICÁCIA DO TREINAMENTO)
        eh_layout_142 = False
        for r in range(1, 4):
            for c in range(1, 6):
                v = str(ws.cell(r, c).value or '').upper()
                if "AVALIA" in v and "EFIC" in v:
                    eh_layout_142 = True
                    break

        if eh_layout_142:
            # Linha 4: Carência / Data devida
            ws.cell(row=4, column=3, value=f"APLICAR APÓS {data_eficacia_str} (CARÊNCIA DE 30 DIAS CALCULADA)")
            # Linha 5: Treinamento e Data
            ws.cell(row=5, column=3, value=f"{proc.codigo} - {proc.nome}" if proc else "-")
            ws.cell(row=5, column=23, value=data_treinamento_str)
            # Linha 6: Participante e Área
            ws.cell(row=6, column=3, value=colab.nome_completo if colab else "-")
            ws.cell(row=6, column=23, value=colab.setor.nome if (colab and colab.setor) else "-")
            # Linha 7: Gestor
            ws.cell(row=7, column=3, value=responsavel_nome)
            # Linha 30: Justificativa / Parecer Gestor
            if treinamento.resultado_avaliacao:
                ws.cell(row=30, column=2, value=treinamento.resultado_avaliacao)
            # Linha 38: Checkboxes de Eficaz / Ineficaz
            if status_str == 'EFICAZ':
                ws.cell(row=38, column=16, value="[ X ]")
            elif status_str == 'INEFICAZ':
                ws.cell(row=38, column=22, value="[ X ]")
            # Linhas 42-44: Assinaturas e Datas
            ws.cell(row=42, column=2, value=f"Colaborador: {colab.nome_completo if colab else '-'}")
            ws.cell(row=42, column=26, value=f"Data: {data_treinamento_str}")
            ws.cell(row=43, column=2, value=f"Gestor: {responsavel_nome}")
            ws.cell(row=43, column=26, value=f"Data: {data_avaliacao_str}")

    else:
        # Gerador nativo de alta fidelidade para FOR.142.r01
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Eficácia FOR.142"

        font_header_doc = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        font_section = Font(name="Arial", size=9.5, bold=True, color="FFFFFF")
        font_label = Font(name="Arial", size=8.5, bold=True, color="334155")
        font_val = Font(name="Arial", size=8.5, color="0F172A")
        font_destaque = Font(name="Arial", size=9, bold=True, color="1E3A8A")

        fill_header_doc = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        fill_section = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        fill_meta = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_calculada = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # Amarelo suave

        border_box = Border(
            left=Side(style='thin', color='000000'),
            right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'),
            bottom=Side(style='thin', color='000000')
        )

        align_center = Alignment(horizontal='center', vertical='center')
        align_left = Alignment(horizontal='left', vertical='center')
        align_top_left = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # 1. Cabeçalho Principal
        ws.merge_cells("A1:G1")
        c_top = ws.cell(row=1, column=1, value="FOR.142.r01 - AVALIAÇÃO DE EFICÁCIA DO TREINAMENTO")
        c_top.font = font_header_doc
        c_top.fill = fill_header_doc
        c_top.alignment = align_center
        ws.row_dimensions[1].height = 28

        # 2. Dados do Colaborador e Treinamento
        dados_header = [
            ("Colaborador:", colab.nome_completo if colab else "-", "Matrícula:", colab.matricula if colab else "-"),
            ("Cargo / Função:", colab.cargo or "-" if colab else "-", "Setor:", colab.setor.nome if (colab and colab.setor) else "-"),
            ("Responsável / Avaliador:", responsavel_nome, "Procedimento:", f"{proc.codigo} - {proc.nome}" if proc else "-"),
            ("Data do Treinamento:", data_treinamento_str, "Data Devida Eficácia (+30d):", data_eficacia_str),
        ]

        for idx, (l1, v1, l2, v2) in enumerate(dados_header, start=2):
            ws.merge_cells(start_row=idx, start_column=2, end_row=idx, end_column=4)
            ws.merge_cells(start_row=idx, start_column=6, end_row=idx, end_column=7)

            ws.cell(row=idx, column=1, value=l1)
            ws.cell(row=idx, column=2, value=v1)
            ws.cell(row=idx, column=5, value=l2)
            c_v2 = ws.cell(row=idx, column=6, value=v2)

            for col in range(1, 8):
                c = ws.cell(row=idx, column=col)
                c.border = border_box
                if col in [1, 5]:
                    c.font = font_label
                    c.fill = fill_meta
                    c.alignment = align_left
                else:
                    c.font = font_val
                    c.alignment = align_left
            
            # Destacar a Data Devida Calculada
            if idx == 5:
                c_v2.fill = fill_calculada
                c_v2.font = Font(name="Arial", size=9, bold=True, color="92400E")

            ws.row_dimensions[idx].height = 18

        ws.row_dimensions[6].height = 6

        # 3. Seção de Avaliação
        ws.merge_cells("A7:G7")
        c_sec = ws.cell(row=7, column=1, value="PARECER TÉCNICO E RESULTADO DA EFICÁCIA (APÓS 30 DIAS)")
        c_sec.font = font_section
        c_sec.fill = fill_section
        c_sec.alignment = align_center
        ws.row_dimensions[7].height = 20

        # Linha de Status de Eficácia
        ws.cell(row=8, column=1, value="Resultado da Eficácia:")
        ws.cell(row=8, column=1).font = font_label
        ws.cell(row=8, column=1).fill = fill_meta
        ws.cell(row=8, column=1).border = border_box

        ws.merge_cells("B8:D8")
        chk_str = f"{'●' if status_str == 'EFICAZ' else '○'} Eficaz     {'●' if status_str == 'INEFICAZ' else '○'} Ineficaz     {'●' if status_str == 'NAO_APLICA' else '○'} Não se Aplica"
        c_chk = ws.cell(row=8, column=2, value=chk_str)
        c_chk.font = font_destaque
        c_chk.alignment = align_left
        for col in range(2, 5):
            ws.cell(row=8, column=col).border = border_box

        ws.cell(row=8, column=5, value="Data da Avaliação:")
        ws.cell(row=8, column=5).font = font_label
        ws.cell(row=8, column=5).fill = fill_meta
        ws.cell(row=8, column=5).border = border_box

        ws.merge_cells("F8:G8")
        c_dt_av = ws.cell(row=8, column=6, value=data_avaliacao_str)
        c_dt_av.font = font_val
        c_dt_av.alignment = align_left
        for col in range(6, 8):
            ws.cell(row=8, column=col).border = border_box
        ws.row_dimensions[8].height = 20

        # Evidências / Justificativas
        ws.merge_cells("A9:G9")
        c_ev_title = ws.cell(row=9, column=1, value="Evidências Objetivas Observadas / Justificativa:")
        c_ev_title.font = font_label
        c_ev_title.fill = fill_meta
        c_ev_title.alignment = align_left
        for col in range(1, 8):
            ws.cell(row=9, column=col).border = border_box
        ws.row_dimensions[9].height = 18

        ws.merge_cells("A10:G15")
        c_ev_body = ws.cell(row=10, column=1, value=treinamento.resultado_avaliacao or "Nenhuma observação ou evidência registrada.")
        c_ev_body.font = font_val
        c_ev_body.alignment = align_top_left
        for r_ev in range(10, 16):
            for col in range(1, 8):
                ws.cell(row=r_ev, column=col).border = border_box
            ws.row_dimensions[r_ev].height = 16

        # Bloco de Assinaturas
        ws.row_dimensions[16].height = 12

        ws.merge_cells("A17:C17")
        ws.merge_cells("E17:G17")

        c_ass_col = ws.cell(row=17, column=1, value="Assinatura do Colaborador Avaliado")
        c_ass_col.font = font_label
        c_ass_col.alignment = align_center

        c_ass_lid = ws.cell(row=17, column=5, value="Assinatura do Líder / Avaliador Responsável")
        c_ass_lid.font = font_label
        c_ass_lid.alignment = align_center

        larguras_142 = {'A': 18, 'B': 22, 'C': 16, 'D': 16, 'E': 20, 'F': 20, 'G': 16}
        for col_letter, width in larguras_142.items():
            ws.column_dimensions[col_letter].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
