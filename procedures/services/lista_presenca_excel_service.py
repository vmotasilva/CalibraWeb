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


def _obter_mapeamento_checkboxes(planejamento: PlanejamentoTreinamento, overrides: dict = None) -> dict:
    """
    Avalia os dados do planejamento, procedimentos e possíveis respostas do usuário
    para determinar os estados dos checkboxes (● ou ○).
    """
    mapping = {}
    overrides = overrides or {}

    # -------------------------------------------------------------
    # 1. Categoria do Treinamento (Treinamento, Reunião, Reciclagem)
    # -------------------------------------------------------------
    cat_override = overrides.get('categoria')
    if cat_override:
        cat_sel = cat_override.upper()
        mapping["{{CHK_TREIN}}"] = CHECK_ON if cat_sel in ['TREIN', 'TREINAMENTO'] else CHECK_OFF
        mapping["{{CHK_REUN}}"] = CHECK_ON if cat_sel in ['REUN', 'REUNIAO', 'REUNIÃO'] else CHECK_OFF
        mapping["{{CHK_RECIC}}"] = CHECK_ON if cat_sel in ['RECIC', 'RECICLAGEM'] else CHECK_OFF
        mapping["{{CHK_INTEGRACAO}}"] = CHECK_ON if cat_sel in ['INTEG', 'INTEGRACAO', 'INTEGRAÇÃO'] else CHECK_OFF
    else:
        origem = (getattr(planejamento, 'origem', '') or '').upper()
        titulo = (planejamento.titulo or '').upper()
        obs = (getattr(planejamento, 'observacoes', '') or '').upper()

        is_reuniao = "REUNIAO" in origem or "REUNIÃO" in titulo or "REUNIAO" in titulo
        is_reciclagem = "RECIC" in origem or "RECICLAGEM" in titulo or "RECICLAGEM" in obs
        is_integracao = "INTEGRACAO" in origem or "INTEGRAÇÃO" in titulo
        is_treinamento = not (is_reuniao or is_reciclagem or is_integracao)

        mapping["{{CHK_TREIN}}"] = CHECK_ON if is_treinamento else CHECK_OFF
        mapping["{{CHK_REUN}}"] = CHECK_ON if is_reuniao else CHECK_OFF
        mapping["{{CHK_RECIC}}"] = CHECK_ON if is_reciclagem else CHECK_OFF
        mapping["{{CHK_INTEGRACAO}}"] = CHECK_ON if is_integracao else CHECK_OFF

    # -------------------------------------------------------------
    # 2. Metodologia (LOFT / Prático vs Tradicional / Teórico)
    # -------------------------------------------------------------
    met_override = overrides.get('metodologia')
    if met_override:
        met_sel = met_override.upper()
        is_loft = met_sel in ['LOFT', 'PRATICA', 'PRÁTICA']
    else:
        metodologia = getattr(planejamento, 'metodologia', '')
        if not metodologia:
            titulo = (planejamento.titulo or '').upper()
            obs = (getattr(planejamento, 'observacoes', '') or '').upper()
            is_loft = "LOFT" in titulo or "LOFT" in obs or "PRAT" in obs
        else:
            is_loft = "LOFT" in str(metodologia).upper() or "PRAT" in str(metodologia).upper()

    mapping["{{CHK_LOFT}}"] = CHECK_ON if is_loft else CHECK_OFF
    mapping["{{CHK_TRAD}}"] = CHECK_OFF if is_loft else CHECK_ON

    # -------------------------------------------------------------
    # 3. Necessita Avaliação de Eficácia (SIM / NÃO)
    # Regra: Deve estar marcado SIM quando houver ao menos um procedimento crítico
    # -------------------------------------------------------------
    aval_override = overrides.get('necessita_avaliacao')
    if aval_override:
        aval_str = str(aval_override).upper()
        necessita_aval = aval_str in ['SIM', 'TRUE', '1', 'S']
    else:
        tem_procedimento_critico = planejamento.procedimentos.filter(criticidade='CRITICO').exists()
        necessita_aval = getattr(
            planejamento, 
            'necessita_avaliacao', 
            getattr(planejamento, 'avaliacao_eficacia', tem_procedimento_critico)
        )

    mapping["{{CHK_AVAL_SIM}}"] = CHECK_ON if bool(necessita_aval) else CHECK_OFF
    mapping["{{CHK_AVAL_NAO}}"] = CHECK_OFF if bool(necessita_aval) else CHECK_ON

    # -------------------------------------------------------------
    # 4. Área de Conhecimento (Administrativo, Qualidade, EHS, Estoque, Produção, Outros)
    # -------------------------------------------------------------
    area_override = overrides.get('area_conhecimento')
    if area_override:
        area_sel = area_override.upper()
        mapping["{{CHK_ADM}}"] = CHECK_ON if area_sel in ['ADM', 'ADMINISTRATIVO', 'RH'] else CHECK_OFF
        mapping["{{CHK_QUALIDADE}}"] = CHECK_ON if area_sel in ['QUALIDADE', 'SGQ', 'ISO'] else CHECK_OFF
        mapping["{{CHK_EHS}}"] = CHECK_ON if area_sel in ['EHS', 'SEGURANCA', 'MEIO_AMBIENTE'] else CHECK_OFF
        mapping["{{CHK_ESTOQUE}}"] = CHECK_ON if area_sel in ['ESTOQUE', 'ALMOXARIFADO', 'LOGISTICA'] else CHECK_OFF
        mapping["{{CHK_PRODUCAO}}"] = CHECK_ON if area_sel in ['PRODUCAO', 'PRODUÇÃO', 'FABRICA'] else CHECK_OFF
        mapping["{{CHK_OUTROS}}"] = CHECK_ON if area_sel in ['OUTROS', 'OUTRO'] else CHECK_OFF
    else:
        areas = [
            (p.area_conhecimento or '').upper() 
            for p in planejamento.procedimentos.all()
        ]
        areas_str = " ".join(areas) + " " + (planejamento.titulo or '').upper() + " " + (getattr(planejamento, 'observacoes', '') or '').upper()

        is_qualidade = "QUALIDADE" in areas_str or "SGQ" in areas_str or "ISO" in areas_str
        is_ehs = "EHS" in areas_str or "SEGURAN" in areas_str or "AMBIENTE" in areas_str
        is_estoque = "ESTOQUE" in areas_str or "ALMOXARIF" in areas_str or "LOGIST" in areas_str
        is_producao = "PRODU" in areas_str or "FABRICA" in areas_str
        is_adm = "ADM" in areas_str or "ADMINISTRATIV" in areas_str or "RH" in areas_str

        # Se nenhuma for detectada, padrão é Qualidade ou Produção conforme o contexto
        if not (is_qualidade or is_ehs or is_estoque or is_producao or is_adm):
            is_qualidade = True

        mapping["{{CHK_ADM}}"] = CHECK_ON if is_adm else CHECK_OFF
        mapping["{{CHK_QUALIDADE}}"] = CHECK_ON if is_qualidade else CHECK_OFF
        mapping["{{CHK_EHS}}"] = CHECK_ON if is_ehs else CHECK_OFF
        mapping["{{CHK_ESTOQUE}}"] = CHECK_ON if is_estoque else CHECK_OFF
        mapping["{{CHK_PRODUCAO}}"] = CHECK_ON if is_producao else CHECK_OFF
        mapping["{{CHK_OUTROS}}"] = CHECK_OFF

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


def gerar_lista_presenca_xlsx(planejamento: PlanejamentoTreinamento, overrides: dict = None) -> BytesIO:
    """Carrega o template e preenche cabeçalhos, checkboxes, participantes e procedimentos."""
    from procedures.models import TemplateDocumentoTreinamento

    wb = None

    # 1. Prioridade: Buscar template ativo configurado na sessão de Templates de Treinamento
    template_config = TemplateDocumentoTreinamento.objects.filter(
        funcao='LISTA_PRESENCA',
        ativo=True
    ).first()

    if template_config and template_config.arquivo:
        try:
            template_config.arquivo.seek(0)
            arquivo_bytes = BytesIO(template_config.arquivo.read())
            wb = openpyxl.load_workbook(arquivo_bytes)
        except Exception:
            wb = None

    # 2. Fallback: Diretórios padrão do sistema de arquivos
    if wb is None:
        nome_arquivo_template = "FOR.033.r07_Lista_de_Presenca_de_Treinamento.xlsx"
        caminhos = [
            os.path.join(settings.BASE_DIR, "templates", nome_arquivo_template),
            os.path.join(settings.BASE_DIR, "procedures", "templates", nome_arquivo_template),
            os.path.join(settings.BASE_DIR, "static", "templates", nome_arquivo_template),
            os.path.join(settings.BASE_DIR, nome_arquivo_template),
            os.path.join(settings.MEDIA_ROOT, "templates_treinamento_docs", nome_arquivo_template),
        ]
        template_path = next((p for p in caminhos if os.path.exists(p)), None)
        if template_path:
            wb = openpyxl.load_workbook(template_path)

    if wb is None:
        raise FileNotFoundError("Nenhum template ativo foi encontrado. Faça o upload do arquivo na sessão de 'Templates de Documentos'.")

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

    # 2. Incorporar os Checkboxes calculados com base nas perguntas/respostas
    checkbox_mapping = _obter_mapeamento_checkboxes(planejamento, overrides=overrides)
    substituicoes.update(checkbox_mapping)

    # Executa a substituição na primeira aba
    _search_and_replace_sheet(ws_frente, substituicoes)

    # 3. Preenchimento dos Participantes (Detecção Flexível de Tags ou Cabeçalhos)
    anchor_row = None
    col_nome = None
    col_cpf_mat = None
    col_cargo = None
    col_setor = None

    # Varredura primária: procurar tags explícitas
    for row in ws_frente.iter_rows():
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                val_upper = cell.value.upper()
                if "{{NOME_PARTICIPANTE}}" in val_upper or "{{NOME_COLABORADOR}}" in val_upper:
                    anchor_row = cell.row
                    col_nome = cell.column
                if "{{MATRICULA_PARTICIPANTE}}" in val_upper or "{{CPF_PARTICIPANTE}}" in val_upper or "{{CPF}}" in val_upper:
                    col_cpf_mat = cell.column
                if "{{CARGO_PARTICIPANTE}}" in val_upper or "{{CARGO}}" in val_upper:
                    col_cargo = cell.column
                if "{{SETOR_PARTICIPANTE}}" in val_upper or "{{DEPARTAMENTO_PARTICIPANTE}}" in val_upper or "{{DEPARTAMENTO}}" in val_upper:
                    col_setor = cell.column

    # Varredura secundária: se não houver tags na linha da tabela, buscar pelos cabeçalhos da tabela
    if not anchor_row:
        for row in ws_frente.iter_rows(max_row=25):
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    val = cell.value.strip().lower()
                    if "nome do colaborador" in val or "nome colaborador" in val:
                        anchor_row = cell.row + 1
                        col_nome = cell.column
                    elif "cpf" in val or "matrícula" in val or "matricula" in val:
                        col_cpf_mat = cell.column
                    elif "cargo" in val or "função" in val or "funcao" in val:
                        col_cargo = cell.column
                    elif "departamento" in val or "setor" in val or "área" in val:
                        col_setor = cell.column

    colaboradores = list(planejamento.colaboradores.select_related("setor").all())

    if anchor_row and col_nome:
        if colaboradores:
            c1 = colaboradores[0]
            ws_frente.cell(row=anchor_row, column=col_nome, value=c1.nome_completo or "")
            if col_cpf_mat:
                ws_frente.cell(row=anchor_row, column=col_cpf_mat, value=c1.cpf or c1.matricula or "")
            if col_cargo:
                ws_frente.cell(row=anchor_row, column=col_cargo, value=c1.cargo or c1.posto_trabalho or "")
            if col_setor:
                ws_frente.cell(row=anchor_row, column=col_setor, value=c1.setor.nome if c1.setor else "")

            for idx, c in enumerate(colaboradores[1:], start=1):
                t_row = anchor_row + idx
                
                # Nome
                cell_n = ws_frente.cell(row=t_row, column=col_nome, value=c.nome_completo or "")
                _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_nome), cell_n)

                # CPF / Matrícula
                if col_cpf_mat:
                    cell_m = ws_frente.cell(row=t_row, column=col_cpf_mat, value=c.cpf or c.matricula or "")
                    _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_cpf_mat), cell_m)

                # Cargo
                if col_cargo:
                    cell_cg = ws_frente.cell(row=t_row, column=col_cargo, value=c.cargo or c.posto_trabalho or "")
                    _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_cargo), cell_cg)

                # Departamento / Setor
                if col_setor:
                    cell_s = ws_frente.cell(row=t_row, column=col_setor, value=c.setor.nome if c.setor else "")
                    _copiar_estilo_celula(ws_frente.cell(row=anchor_row, column=col_setor), cell_s)
        else:
            ws_frente.cell(row=anchor_row, column=col_nome, value="")
            if col_cpf_mat:
                ws_frente.cell(row=anchor_row, column=col_cpf_mat, value="")
            if col_cargo:
                ws_frente.cell(row=anchor_row, column=col_cargo, value="")
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
