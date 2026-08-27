# -*- coding: utf-8 -*-
"""
Serviço de Geração de Lista de Presença em Excel
Baseado em substituição de tags dinâmicas no template FOR.033.r07
"""

import os
from io import BytesIO
from copy import copy
import openpyxl
from django.conf import settings
from procedures.models import PlanejamentoTreinamento

# Constantes Unicode para Marcação de Checkboxes / Radios
CHECK_ON = "●"   # \u25cf
CHECK_OFF = "○"  # \u25cb


def _obter_mapeamento_checkboxes(planejamento: PlanejamentoTreinamento) -> dict:
    """
    Avalia os dados do planejamento e dos procedimentos relacionados para
    determinar os estados dos checkboxes (● ou ○).
    """
    mapping = {}

    # 1. Tipo / Categoria do Treinamento
    origem = (getattr(planejamento, 'origem', '') or '').upper()
    titulo = (planejamento.titulo or '').upper()
    obs = (getattr(planejamento, 'observacoes', '') or '').upper()

    is_reuniao = "REUNIAO" in origem or "REUNIÃO" in titulo or "REUNIAO" in titulo
    is_reciclagem = "RECIC" in origem or "RECICLAGEM" in titulo or "RECICLAGEM" in obs
    is_integracao = "INTEGRACAO" in origem or "INTEGRAÇÃO" in titulo

    # Padrão: Se não for reunião, reciclagem ou integração, considera Treinamento
    is_treinamento = not (is_reuniao or is_reciclagem or is_integracao)

    mapping["{{CHK_TREIN}}"] = CHECK_ON if is_treinamento else CHECK_OFF
    mapping["{{CHK_REUN}}"] = CHECK_ON if is_reuniao else CHECK_OFF
    mapping["{{CHK_RECIC}}"] = CHECK_ON if is_reciclagem else CHECK_OFF
    mapping["{{CHK_INTEGRACAO}}"] = CHECK_ON if is_integracao else CHECK_OFF

    # 2. Metodologia (LOFT / Prático vs Tradicional / Teórico)
    metodologia = getattr(planejamento, 'metodologia', '')
    if not metodologia:
        metodologia = "LOFT" if ("LOFT" in titulo or "LOFT" in obs or "PRAT" in obs) else "TRAD"
    else:
        metodologia = str(metodologia).upper()

    is_loft = "LOFT" in metodologia or "PRAT" in metodologia
    mapping["{{CHK_LOFT}}"] = CHECK_ON if is_loft else CHECK_OFF
    mapping["{{CHK_TRAD}}"] = CHECK_OFF if is_loft else CHECK_ON

    # 3. Necessita Avaliação de Eficácia (SIM / NÃO)
    tem_procedimento_critico = planejamento.procedimentos.filter(criticidade='CRITICO').exists()
    necessita_aval = getattr(
        planejamento, 
        'necessita_avaliacao', 
        getattr(planejamento, 'avaliacao_eficacia', tem_procedimento_critico)
    )

    mapping["{{CHK_AVAL_SIM}}"] = CHECK_ON if bool(necessita_aval) else CHECK_OFF
    mapping["{{CHK_AVAL_NAO}}"] = CHECK_OFF if bool(necessita_aval) else CHECK_ON

    # 4. Área de Conhecimento
    areas = [
        (p.area_conhecimento or '').upper() 
        for p in planejamento.procedimentos.all()
    ]
    areas_str = " ".join(areas) + " " + titulo + " " + obs

    is_qualidade = "QUALIDADE" in areas_str or "SGQ" in areas_str or "ISO" in areas_str
    is_adm = "ADM" in areas_str or "ADMINISTRATIV" in areas_str or "RH" in areas_str
    is_producao = "PRODU" in areas_str or "FABRICA" in areas_str
    is_operacional = "OPERACIONAL" in areas_str or "TECNIC" in areas_str or "LAB" in areas_str

    mapping["{{CHK_QUALIDADE}}"] = CHECK_ON if is_qualidade else CHECK_OFF
    mapping["{{CHK_ADM}}"] = CHECK_ON if is_adm else CHECK_OFF
    mapping["{{CHK_PRODUCAO}}"] = CHECK_ON if is_producao else CHECK_OFF
    mapping["{{CHK_OPERACIONAL}}"] = CHECK_ON if is_operacional else CHECK_OFF

    return mapping


def _search_and_replace_sheet(sheet, mapping: dict):
    """
    Substitui todas as tags de texto e checkboxes nas células da planilha.
    """
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                valor = str(cell.value)
                for tag, novo_valor in mapping.items():
                    if tag in valor:
                        valor = valor.replace(tag, str(novo_valor if novo_valor is not None else ''))
                cell.value = valor


def _copiar_estilo_celula(origem, destino):
    """Copia a formatação da célula âncora para as novas linhas."""
    if origem.has_style:
        destino.font = copy(origem.font)
        destino.border = copy(origem.border)
        destino.fill = copy(origem.fill)
        destino.number_format = copy(origem.number_format)
        destino.protection = copy(origem.protection)
        destino.alignment = copy(origem.alignment)


def gerar_lista_presenca_xlsx(planejamento: PlanejamentoTreinamento) -> BytesIO:
    """Carrega o template e preenche cabeçalhos, checkboxes, participantes e procedimentos."""
    nome_arquivo_template = "FOR.033.r07_Lista_de_Presenca_de_Treinamento.xlsx"
    caminhos = [
        os.path.join(settings.BASE_DIR, "templates", nome_arquivo_template),
        os.path.join(settings.BASE_DIR, "procedures", "templates", nome_arquivo_template),
        os.path.join(settings.BASE_DIR, "static", "templates", nome_arquivo_template),
        os.path.join(settings.BASE_DIR, nome_arquivo_template),
    ]

    template_path = next((p for p in caminhos if os.path.exists(p)), None)
    if not template_path:
        raise FileNotFoundError(f"Template '{nome_arquivo_template}' não encontrado nos diretórios do sistema.")

    wb = openpyxl.load_workbook(template_path)
    ws_frente = wb.worksheets[0]

    # 1. Montar substituição de texto e dados básicos
    data_hora_str = (
        planejamento.horario_previsto.strftime("%d/%m/%Y %H:%M")
        if planejamento.horario_previsto
        else (planejamento.data_prevista.strftime("%d/%m/%Y") if planejamento.data_prevista else "")
    )
    carga_horaria_str = f"{planejamento.carga_horaria} Minutos" if planejamento.carga_horaria else ""
    instrutor_nome = planejamento.instrutor.nome_completo if planejamento.instrutor else ""

    substituicoes = {
        "{{TITULO}}": planejamento.titulo or "",
        "{{INSTRUTOR}}": instrutor_nome,
        "{{DATA_HORA}}": data_hora_str,
        "{{CARGA_HORARIA}}": carga_horaria_str,
    }

    # 2. Incorporar os Checkboxes calculados
    checkbox_mapping = _obter_mapeamento_checkboxes(planejamento)
    substituicoes.update(checkbox_mapping)

    # Executa a substituição na primeira aba
    _search_and_replace_sheet(ws_frente, substituicoes)

    # 3. Preenchimento dos Participantes (Linha Âncora)
    anchor_row = None
    col_nome = None
    col_matricula = None
    col_setor = None

    for row in ws_frente.iter_rows():
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                if "{{NOME_PARTICIPANTE}}" in cell.value:
                    anchor_row = cell.row
                    col_nome = cell.column
                if "{{MATRICULA_PARTICIPANTE}}" in cell.value:
                    col_matricula = cell.column
                if "{{SETOR_PARTICIPANTE}}" in cell.value:
                    col_setor = cell.column

    colaboradores = list(planejamento.colaboradores.select_related("setor").all())

    if anchor_row and col_nome:
        if colaboradores:
            c1 = colaboradores[0]
            ws_frente.cell(row=anchor_row, column=col_nome, value=c1.nome_completo or "")
            if col_matricula:
                ws_frente.cell(row=anchor_row, column=col_matricula, value=c1.matricula or "")
            if col_setor:
                ws_frente.cell(row=anchor_row, column=col_setor, value=c1.setor.nome if c1.setor else "")

            for idx, c in enumerate(colaboradores[1:], start=1):
                t_row = anchor_row + idx
                cell_n = ws_frente.cell(row=t_row, column=col_nome, value=c.nome_completo or "")
                _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_nome), cell_n)

                if col_matricula:
                    cell_m = ws_frente.cell(row=t_row, column=col_matricula, value=c.matricula or "")
                    _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_matricula), cell_m)
                if col_setor:
                    cell_s = ws_frente.cell(row=t_row, column=col_setor, value=c.setor.nome if c.setor else "")
                    _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_setor), cell_s)
        else:
            ws_frente.cell(row=anchor_row, column=col_nome, value="")
            if col_matricula:
                ws_frente.cell(row=anchor_row, column=col_matricula, value="")
            if col_setor:
                ws_frente.cell(row=anchor_row, column=col_setor, value="")

    # 4. Preenchimento dos Procedimentos (Verso - worksheets[1])
    if len(wb.worksheets) > 1:
        ws_verso = wb.worksheets[1]
        _search_and_replace_sheet(ws_verso, substituicoes)

        proc_anchor_row = None
        proc_col = None

        for row in ws_verso.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    if "{{PROCEDIMENTOS}}" in cell.value:
                        proc_anchor_row = cell.row
                        proc_col = cell.column
                        break
            if proc_anchor_row:
                break

        procedimentos = list(planejamento.procedimentos.all())
        if proc_anchor_row and proc_col:
            if procedimentos:
                p1 = procedimentos[0]
                ws_verso.cell(row=proc_anchor_row, column=proc_col, value=f"{p1.codigo or ''} - {p1.nome or ''}".strip(" -"))

                for idx, p in enumerate(procedimentos[1:], start=1):
                    t_row = proc_anchor_row + idx
                    texto_proc = f"{p.codigo or ''} - {p.nome or ''}".strip(" -")
                    cell_p = ws_verso.cell(row=t_row, column=proc_col, value=texto_proc)
                    _copiar_estilo_celula(ws_verso.cell(row=proc_anchor_row, column=proc_col), cell_p)
            else:
                ws_verso.cell(row=proc_anchor_row, column=proc_col, value="")

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
