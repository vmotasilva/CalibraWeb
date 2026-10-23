"""Templates de página: planilhas (.xlsx) com variáveis de marcação que o sistema preenche com o PCP de uma página.

Segue a prática da lista de presença de Treinamentos: o template é um Excel com tags ``{{TAG}}`` nas células (e em caixas de texto);
o sistema substitui as tags e replica uma **linha âncora** (copiando o estilo) para listar os itens.

Tags (maiúsculas; espaços dentro das chaves são aceitos):

- Cabeçalho, em qualquer célula ou caixa de texto: FORMULARIO_CODIGO, FORMULARIO_TITULO, REVISAO, SETOR, PAGINA, GRUPO, MAQUINA,
  CODIGO_SISTEMA, MES, MES_NOME, ANO, DATA_INICIO, DATA_FIM, DATA_EXTRACAO, TOTAL_ITENS; DIA:n (data do dia n do mês, dd/mm) e
  DIASEMANA:n (seg, ter…), com n de 1 a 31.
- Linha âncora (a primeira linha da aba que tiver alguma tag de item): NUM (Nº do item no bloco), ITEM, ETAPA, DESCRICAO, ESPECIFICACAO,
  METODO, FREQUENCIA, PLANO_REACAO, RESPONSAVEL, UNIDADE, MINIMO, MAXIMO, CRITICO, TIPO. Ela é repetida para cada item da página.
- Modo grade (como as planilhas originais, itens nas linhas e dias/turnos nas colunas): VALOR:n:T e STATUS:n:T na linha âncora, com n o dia
  do mês e T a sigla do turno (T1, T2…) ou a posição dele (1, 2…).
- Modo lista (uma linha por item, data e turno preenchidos): DATA, TURNO, VALOR e STATUS (sem parâmetros) na linha âncora.

Turnos em Em Manutenção/Parada preenchem VALOR com a situação da máquina. Abas cujo nome começa com "_" são documentação: não vão para a saída.
"""
import base64
import datetime
import re
from copy import copy
from io import BytesIO

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.cell_range import CellRange

from pcp.exportacao import COR_STATUS, ROTULOS, _valor_celula, lancamentos_da_pagina, periodo_do_mes
from pcp.models import Turno
from pcp.pendencias import chave

RE_TAG = re.compile(r'\{\{\s*([A-Za-z_]+(?:\s*:\s*[A-Za-z0-9_]+){0,2})\s*\}\}')

ESCALARES = {
    'FORMULARIO_CODIGO': 'Código do formulário (ex.: FOR.080)', 'FORMULARIO_TITULO': 'Título do formulário', 'REVISAO': 'Revisão (ex.: R15)',
    'SETOR': 'Setor do formulário', 'PAGINA': 'Nome da página (equipamento)', 'GRUPO': 'Grupo da página', 'MAQUINA': 'Máquina vinculada à página',
    'CODIGO_SISTEMA': 'Código da página no sistema', 'MES': 'Mês e ano (10/2026)', 'MES_NOME': 'Mês por extenso (outubro de 2026)', 'ANO': 'Ano',
    'DATA_INICIO': 'Primeiro dia do mês', 'DATA_FIM': 'Último dia do mês', 'DATA_EXTRACAO': 'Data em que a planilha foi gerada',
    'TOTAL_ITENS': 'Quantidade de itens ativos da página'}
ITENS = {
    'NUM': 'Nº do item no bloco', 'ITEM': 'Código do item', 'ETAPA': 'Etapa / contexto', 'DESCRICAO': 'O que verificar', 'ESPECIFICACAO': 'Especificação',
    'METODO': 'Método de verificação', 'FREQUENCIA': 'Frequência', 'PLANO_REACAO': 'Plano de reação', 'RESPONSAVEL': 'Responsável',
    'UNIDADE': 'Unidade', 'MINIMO': 'Limite mínimo', 'MAXIMO': 'Limite máximo', 'CRITICO': '"Sim" para item crítico', 'TIPO': 'Tipo do campo'}
LISTA = {'DATA': 'Data (modo lista)', 'TURNO': 'Sigla do turno (modo lista)', 'VALOR': 'Valor lançado ou situação da máquina (modo lista)',
         'STATUS': 'Situação da máquina: Em Manutenção, Parada ou vazio (modo lista)'}
MESES_NOME = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']


def normalizar(tag):
    return re.sub(r'\s+', '', tag).upper()


def classificar(tag):
    """'escalar', 'dia' (DIA:n, DIASEMANA:n), 'item', 'grade' (VALOR:n:T, STATUS:n:T), 'lista' ou 'desconhecida'."""
    base, *params = tag.split(':')
    if not params:
        if base in ESCALARES:
            return 'escalar'
        if base in ITENS:
            return 'item'
        if base in LISTA:
            return 'lista'
    elif base in ('DIA', 'DIASEMANA') and len(params) == 1 and params[0].isdigit() and 1 <= int(params[0]) <= 31:
        return 'dia'
    elif base in ('VALOR', 'STATUS') and len(params) == 2 and params[0].isdigit() and 1 <= int(params[0]) <= 31 and params[1]:
        return 'grade'
    return 'desconhecida'


def _celulas_com_texto(ws):
    for linha in ws.iter_rows():
        for c in linha:
            if isinstance(c.value, str) and '{{' in c.value:
                yield c


def tags_do_workbook(wb):
    """{categoria: {tags}} de todas as abas de saída (abas que começam com '_' são documentação)."""
    achadas = {}
    for ws in wb.worksheets:
        if ws.title.startswith('_'):
            continue
        for c in _celulas_com_texto(ws):
            for m in RE_TAG.finditer(c.value):
                tag = normalizar(m.group(1))
                achadas.setdefault(classificar(tag), set()).add(tag)
    return achadas


def analisar(conteudo):
    """Resumo de um template: tags reconhecidas/desconhecidas e modo. Levanta ValueError se o arquivo não for um .xlsx legível."""
    try:
        wb = openpyxl.load_workbook(BytesIO(conteudo))
    except Exception as e:
        raise ValueError('Não foi possível ler o arquivo: envie uma planilha .xlsx válida.') from e
    achadas = tags_do_workbook(wb)
    reconhecidas = sorted(t for cat, ts in achadas.items() if cat != 'desconhecida' for t in ts)
    linha = achadas.get('item', set()) | achadas.get('grade', set()) | achadas.get('lista', set())
    modo = ''
    if any(not w.title.startswith('_') and achar_calendario(w) for w in wb.worksheets):
        modo = 'calendario'
    elif achadas.get('lista'):
        modo = 'lista'
    elif achadas.get('item') or achadas.get('grade'):
        modo = 'grade'
    avisos = []
    if not reconhecidas:
        raise ValueError('Nenhuma variável {{TAG}} reconhecida no template. Veja o modelo de exemplo para saber como marcar o arquivo.')
    if not linha:
        avisos.append('Nenhuma tag de item na planilha: só o cabeçalho será preenchido (use NUM, ITEM, DESCRICAO… na linha dos itens).')
    if modo == 'calendario':
        avisos.append('Modo calendário: o primeiro bloco de colunas é o modelo; cada data do período ganha um bloco igual e o sistema gera uma aba por página.')
    if achadas.get('lista') and achadas.get('grade') and modo != 'calendario':
        avisos.append('Há tags do modo grade e do modo lista na mesma planilha; cada aba usa o modo da sua linha âncora.')
    return {'tags': reconhecidas, 'desconhecidas': sorted(achadas.get('desconhecida', set())), 'modo': modo, 'abas': len(
        [w for w in wb.worksheets if not w.title.startswith('_')]), 'avisos': avisos}


def codificar(conteudo):
    return base64.b64encode(conteudo).decode('ascii')


def decodificar(texto):
    return base64.b64decode(texto.encode('ascii'))


# --------------------------------------------------------------------------------------
# Geração
# --------------------------------------------------------------------------------------

def _escalares(formulario, versao, pagina, ini, fim, dias, campos, hoje):
    d = {
        'FORMULARIO_CODIGO': formulario.codigo, 'FORMULARIO_TITULO': formulario.titulo, 'REVISAO': versao.revisao,
        'SETOR': str(formulario.setor), 'PAGINA': pagina.nome, 'GRUPO': pagina.grupo,
        'MAQUINA': pagina.maquina.display_name if pagina.maquina_id else '', 'CODIGO_SISTEMA': pagina.codigo_sistema,
        'MES': f'{ini:%m/%Y}', 'MES_NOME': f'{MESES_NOME[ini.month - 1]} de {ini.year}', 'ANO': str(ini.year),
        'DATA_INICIO': f'{ini:%d/%m/%Y}', 'DATA_FIM': f'{fim:%d/%m/%Y}', 'DATA_EXTRACAO': f'{hoje:%d/%m/%Y}', 'TOTAL_ITENS': str(len(campos))}
    for n in range(1, 32):
        dia = dias[n - 1] if n <= len(dias) else None
        d[f'DIA:{n}'] = f'{dia:%d/%m}' if dia else ''
        d[f'DIASEMANA:{n}'] = DIAS_SEMANA[dia.weekday()] if dia else ''
    return d


def _substituir(texto, resolver):
    """Se a célula é exatamente uma tag, devolve o valor tipado; senão substitui as tags dentro do texto."""
    completo = RE_TAG.fullmatch(texto.strip())
    if completo:
        valor = resolver(normalizar(completo.group(1)), True)
        return '' if valor is None else valor
    return RE_TAG.sub(lambda m: str('' if (v := resolver(normalizar(m.group(1)), False)) is None else v), texto)


def _preencher_escalares(ws, escalares, ignorar_linha=None):
    def resolver(tag, _):
        if classificar(tag) in ('escalar', 'dia'):
            return escalares[tag]
        return '{{' + tag + '}}'            # tags de linha ficam para a expansão
    for c in list(_celulas_com_texto(ws)):
        if ignorar_linha and c.row == ignorar_linha:
            continue                       # a linha âncora é resolvida junto com os itens
        novo = _substituir(c.value, resolver)
        if novo != c.value:
            c.value = novo


def _achar_ancora(ws):
    """(linha, modo) da primeira linha com tags de item/grade/lista; None se não houver."""
    for linha in ws.iter_rows():
        categorias = set()
        for c in linha:
            if isinstance(c.value, str) and '{{' in c.value:
                categorias |= {classificar(normalizar(m.group(1))) for m in RE_TAG.finditer(c.value)}
        if categorias & {'item', 'grade', 'lista'}:
            return linha[0].row, ('lista' if 'lista' in categorias else 'grade')
    return None


def _abrir_linhas(ws, linha, extra):
    """Insere `extra` linhas depois da âncora, deslocando mesclagens e alturas e copiando estilo e conteúdo da âncora."""
    if extra <= 0:
        return
    mesclagens = list(ws.merged_cells.ranges)
    abaixo = [m for m in mesclagens if m.min_row > linha]
    na_ancora = [m for m in mesclagens if m.min_row == m.max_row == linha]
    for m in abaixo:
        ws.unmerge_cells(str(m))
    alturas = {r: ws.row_dimensions[r].height for r in range(linha, ws.max_row + 1) if ws.row_dimensions[r].height is not None}
    ws.insert_rows(linha + 1, amount=extra)
    for r in sorted((r for r in alturas if r > linha), reverse=True):
        ws.row_dimensions[r + extra].height = alturas[r]
    for m in abaixo:
        ws.merge_cells(start_row=m.min_row + extra, start_column=m.min_col, end_row=m.max_row + extra, end_column=m.max_col)
    for k in range(1, extra + 1):
        if linha in alturas:
            ws.row_dimensions[linha + k].height = alturas[linha]
        for origem in ws[linha]:
            destino = ws.cell(row=linha + k, column=origem.column)
            if origem.has_style:
                destino.font, destino.border, destino.fill = copy(origem.font), copy(origem.border), copy(origem.fill)
                destino.number_format, destino.protection, destino.alignment = origem.number_format, copy(origem.protection), copy(origem.alignment)
        for m in na_ancora:
            ws.merge_cells(start_row=linha + k, start_column=m.min_col, end_row=linha + k, end_column=m.max_col)


def gerar(conteudo_template, formulario, versao, pagina, ano, mes, hoje=None):
    """Preenche o template com o PCP da página no mês e devolve o .xlsx (BytesIO)."""
    from procedures.services.treinamento_excel_export_service import _substituir_tags_no_arquivo_zip
    hoje = hoje or datetime.date.today()
    ini, fim = periodo_do_mes(ano, mes)
    if eh_calendario(conteudo_template):
        return gerar_calendario(conteudo_template, formulario, versao, [pagina], ini, fim, hoje)
    dias = [ini + datetime.timedelta(days=n) for n in range((fim - ini).days + 1)]
    turnos = list(Turno.objects.filter(ativo=True))
    campos = list(pagina.campos.filter(ativo=True).select_related('frequencia').order_by('ordem', 'pk'))
    respostas, parados = lancamentos_da_pagina(formulario, pagina, ini, fim)
    escalares = _escalares(formulario, versao, pagina, ini, fim, dias, campos, hoje)

    def turno_de(texto):
        texto = texto.upper()
        if texto.isdigit():
            n = int(texto)
            return turnos[n - 1] if 1 <= n <= len(turnos) else None
        return next((t for t in turnos if t.sigla.upper() == texto), None)

    def situacao(campo, dia, turno):
        """(valor, status, conforme) do item no dia e turno."""
        status = parados.get((dia, turno.pk))
        if status:
            return ROTULOS[status], status, None
        lancado = respostas.get(chave(campo.item, campo.etapa, campo.descricao), {}).get((dia, turno.pk))
        return (_valor_celula(campo, lancado[0]), '', lancado[1]) if lancado else ('', '', None)

    wb = openpyxl.load_workbook(BytesIO(conteudo_template))
    for ws in [w for w in wb.worksheets if w.title.startswith('_')]:
        wb.remove(ws)
    if not wb.worksheets:
        raise ValueError('O template só tem abas de documentação (nome começando com "_").')

    for ws in wb.worksheets:
        ancora = _achar_ancora(ws)
        _preencher_escalares(ws, escalares, ignorar_linha=ancora[0] if ancora else None)
        if not ancora:
            continue
        linha, modo = ancora
        celulas = [(c.column, c.value) for c in ws[linha] if isinstance(c.value, str) and '{{' in c.value]
        if modo == 'lista':
            registros = []
            for dia in dias:
                for turno in turnos:
                    for campo in campos:
                        valor, status, conforme = situacao(campo, dia, turno)
                        if valor not in ('', None):
                            registros.append((campo, dia, turno, valor, status, conforme))
        else:
            registros = [(campo, None, None, None, '', None) for campo in campos]
        if not registros:
            for coluna, _ in celulas:
                ws.cell(row=linha, column=coluna).value = None
            continue
        _abrir_linhas(ws, linha, len(registros) - 1)
        for k, (campo, dia_l, turno_l, valor_l, status_l, conforme_l) in enumerate(registros):
            for coluna, texto in celulas:
                cel = ws.cell(row=linha + k, column=coluna)
                estado = {}

                def resolver(tag, inteira, campo=campo, dia_l=dia_l, turno_l=turno_l, valor_l=valor_l, status_l=status_l, conforme_l=conforme_l, estado=estado):
                    cat = classificar(tag)
                    if cat in ('escalar', 'dia'):
                        return escalares[tag]
                    base, *params = tag.split(':')
                    if cat == 'item':
                        return {
                            'NUM': campo.ordem, 'ITEM': campo.item, 'ETAPA': campo.etapa, 'DESCRICAO': campo.descricao,
                            'ESPECIFICACAO': campo.especificacao, 'METODO': campo.metodo, 'FREQUENCIA': str(campo.frequencia or ''),
                            'PLANO_REACAO': campo.plano_reacao, 'RESPONSAVEL': campo.responsavel, 'UNIDADE': campo.unidade,
                            'MINIMO': float(campo.minimo) if campo.minimo is not None else '',
                            'MAXIMO': float(campo.maximo) if campo.maximo is not None else '',
                            'CRITICO': 'Sim' if campo.critico else '', 'TIPO': campo.get_tipo_display()}[base]
                    if cat == 'lista':
                        if base == 'DATA':
                            estado['formato'] = 'dd/mm/yyyy'
                            return dia_l
                        if base == 'TURNO':
                            return turno_l.sigla
                        if base == 'STATUS':
                            return ROTULOS.get(status_l, '')
                        estado.update(status=status_l, conforme=conforme_l)
                        return valor_l
                    if cat == 'grade':
                        n = int(params[0])
                        turno = turno_de(params[1])
                        if n > len(dias) or turno is None:
                            return ''
                        valor, status, conforme = situacao(campo, dias[n - 1], turno)
                        if base == 'STATUS':
                            return ROTULOS.get(status, '')
                        estado.update(status=status, conforme=conforme)
                        return valor
                    return '{{' + tag + '}}'

                cel.value = _substituir(texto, resolver)
                if estado.get('formato'):
                    cel.number_format = estado['formato']
                if estado.get('status'):
                    cel.fill = PatternFill('solid', fgColor=COR_STATUS[estado['status']])
                    cel.alignment = Alignment(horizontal='center', vertical='center', shrink_to_fit=True)
                elif estado.get('conforme') is False:
                    cel.font = Font(color='C00000', bold=True)

    bruto = BytesIO()
    wb.save(bruto)
    return _substituir_tags_no_arquivo_zip(bruto.getvalue(), {'{{' + k + '}}': v for k, v in escalares.items()})


# --------------------------------------------------------------------------------------
# Modelo de exemplo
# --------------------------------------------------------------------------------------

def gerar_amostra():
    """Template de exemplo com todas as variáveis: modo grade (aba 'Página'), modo lista (aba 'Modo lista') e a documentação ('_VARIÁVEIS')."""
    turnos = list(Turno.objects.filter(ativo=True)) or [type('T', (), {'sigla': s})() for s in ('T1', 'T2', 'T3')]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Página'
    cab = PatternFill('solid', fgColor='14284B')
    branco = Font(bold=True, color='FFFFFF')
    ws['A1'] = '{{FORMULARIO_CODIGO}} · {{REVISAO}} — {{PAGINA}}'
    ws['A1'].font = Font(bold=True, size=13)
    ws['A2'] = 'Grupo: {{GRUPO}} · Setor: {{SETOR}} · Mês: {{MES_NOME}} · Máquina: {{MAQUINA}}'
    fixas = ['Nº', 'Item', 'O que verificar', 'Especificação', 'Frequência']
    ancora = ['{{NUM}}', '{{ITEM}}', '{{DESCRICAO}}', '{{ESPECIFICACAO}}', '{{FREQUENCIA}}']
    for j, titulo in enumerate(fixas, 1):
        for linha in (4, 5):
            c = ws.cell(row=linha, column=j, value=titulo if linha == 4 else None)
            c.font, c.fill = branco, cab
        ws.cell(row=6, column=j, value=ancora[j - 1])
    for n, largura in zip(range(1, 6), (6, 9, 40, 34, 18)):
        ws.column_dimensions[get_column_letter(n)].width = largura
    col = len(fixas) + 1
    for dia in range(1, 32):
        ws.merge_cells(start_row=4, start_column=col, end_row=4, end_column=col + len(turnos) - 1)
        c = ws.cell(row=4, column=col, value='{{DIA:%d}}' % dia)
        c.font, c.fill, c.alignment = branco, cab, Alignment(horizontal='center')
        for k, t in enumerate(turnos):
            s = ws.cell(row=5, column=col + k, value=t.sigla)
            s.font, s.fill, s.alignment = branco, cab, Alignment(horizontal='center')
            ws.cell(row=6, column=col + k, value='{{VALOR:%d:%s}}' % (dia, t.sigla)).alignment = Alignment(horizontal='center')
            ws.column_dimensions[get_column_letter(col + k)].width = 8
        col += len(turnos)
    ws['A8'] = 'Extraído em {{DATA_EXTRACAO}} · {{TOTAL_ITENS}} itens'
    ws['A8'].font = Font(italic=True, color='666666')
    ws.freeze_panes = 'F6'

    lista = wb.create_sheet('Modo lista')
    titulos = ['Formulário', 'Página', 'Nº', 'Item', 'Data', 'Turno', 'Valor', 'Situação da máquina']
    tags = ['{{FORMULARIO_CODIGO}}', '{{PAGINA}}', '{{NUM}}', '{{ITEM}}', '{{DATA}}', '{{TURNO}}', '{{VALOR}}', '{{STATUS}}']
    for j, (t, tag) in enumerate(zip(titulos, tags), 1):
        c = lista.cell(row=1, column=j, value=t)
        c.font, c.fill = branco, cab
        lista.cell(row=2, column=j, value=tag)
        lista.column_dimensions[get_column_letter(j)].width = 16

    doc = wb.create_sheet('_VARIÁVEIS')
    doc.append(['Variável (use entre chaves duplas, ex.: {{PAGINA}})', 'Onde usar', 'O que preenche'])
    for c in doc[1]:
        c.font, c.fill = branco, cab
    for tag, texto in ESCALARES.items():
        doc.append([tag, 'Qualquer célula ou caixa de texto', texto])
    doc.append(['DIA:n (n de 1 a 31)', 'Cabeçalho das colunas de dias', 'Data do dia n do mês (dd/mm); vazio se o mês não tem o dia'])
    doc.append(['DIASEMANA:n', 'Cabeçalho das colunas de dias', 'Dia da semana do dia n (seg, ter…)'])
    for tag, texto in ITENS.items():
        doc.append([tag, 'Linha âncora (repetida para cada item)', texto])
    doc.append(['VALOR:n:T', 'Linha âncora, modo grade', 'Valor do dia n e turno T (sigla T1/T2… ou posição 1/2…); turno em manutenção/parada traz a situação'])
    doc.append(['STATUS:n:T', 'Linha âncora, modo grade', 'Situação da máquina no dia n e turno T'])
    for tag, texto in LISTA.items():
        doc.append([tag, 'Linha âncora, modo lista', texto])
    doc.append([])
    doc.append(['Regras', '', ''])
    doc.append(['Linha âncora', '', 'A primeira linha da aba com tag de item/valor é repetida para cada item (modo grade) ou para cada item, data e turno preenchidos (modo lista).'])
    doc.append(['Abas "_"', '', 'Abas cujo nome começa com "_" (como esta) são documentação e não vão para a planilha gerada.'])
    for coluna, largura in zip('ABC', (34, 40, 90)):
        doc.column_dimensions[coluna].width = largura
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------------------
# Modo calendário: datas nas colunas (um bloco de colunas por data, uma coluna por turno)
# --------------------------------------------------------------------------------------
# Reconhecido sozinho, sem configuração: {{DATA}} (e {{TURNO}}) nas linhas de cabeçalho acima da linha âncora e {{VALOR}} na linha âncora.
# O primeiro bloco do template é o modelo: cada data do período recebe um bloco igual (mesmo estilo, mesclagens e larguras) e cada turno uma
# coluna; as tags só precisam estar na primeira coluna do bloco. O sistema gera uma aba por página, com o layout do template.

def _tags_da_linha(linha):
    achadas = {}
    for c in linha:
        if isinstance(c.value, str) and '{{' in c.value:
            for m in RE_TAG.finditer(c.value):
                achadas.setdefault(normalizar(m.group(1)), []).append(c.column)
    return achadas


def achar_calendario(ws):
    """Geometria do modo calendário da aba, ou None: linha âncora (com VALOR/STATUS), linha da DATA, linha do TURNO e coluna do 1º bloco."""
    linha_data = linha_turno = col_ini = None
    for linha in ws.iter_rows():
        tags = _tags_da_linha(linha)
        tem_valor = bool({'VALOR', 'STATUS'} & set(tags))
        if 'DATA' in tags and not tem_valor and linha_data is None:
            linha_data, col_ini = linha[0].row, min(tags['DATA'])
        elif 'TURNO' in tags and not tem_valor and linha_turno is None and linha_data is not None:
            linha_turno = linha[0].row
        elif tem_valor:
            if linha_data is None:
                return None
            return {'ancora': linha[0].row, 'linha_data': linha_data, 'linha_turno': linha_turno, 'col_ini': col_ini}
    return None


def eh_calendario(conteudo):
    try:
        wb = openpyxl.load_workbook(BytesIO(conteudo))
    except Exception:
        return False
    return any(not ws.title.startswith('_') and achar_calendario(ws) for ws in wb.worksheets)


def _largura_coluna(ws, col):
    for d in ws.column_dimensions.values():
        if d.min is not None and d.min <= col <= (d.max or d.min) and d.width:
            return d.width
    return None


def _tag_item(tag, campo, escalares):
    cat = classificar(tag)
    if cat in ('escalar', 'dia'):
        return escalares[tag]
    if cat == 'item' and campo is not None:
        return {
            'NUM': campo.ordem, 'ITEM': campo.item, 'ETAPA': campo.etapa, 'DESCRICAO': campo.descricao,
            'ESPECIFICACAO': campo.especificacao, 'METODO': campo.metodo, 'FREQUENCIA': str(campo.frequencia or ''),
            'PLANO_REACAO': campo.plano_reacao, 'RESPONSAVEL': campo.responsavel, 'UNIDADE': campo.unidade,
            'MINIMO': float(campo.minimo) if campo.minimo is not None else '',
            'MAXIMO': float(campo.maximo) if campo.maximo is not None else '',
            'CRITICO': 'Sim' if campo.critico else '', 'TIPO': campo.get_tipo_display()}[tag]
    return ''


def gerar_calendario(conteudo_template, formulario, versao, paginas, ini, fim, hoje=None):
    """Planilha com uma aba por página (layout do template em calendário) para o período ini..fim. Devolve BytesIO."""
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.hyperlink import Hyperlink
    from pcp.exportacao import _nome_aba
    hoje = hoje or datetime.date.today()
    if fim < ini:
        raise ValueError('A data final é anterior à inicial.')
    if not paginas:
        raise ValueError('Nenhuma página ativa atende a este template.')
    wb = openpyxl.load_workbook(BytesIO(conteudo_template))
    mestre = next((ws for ws in wb.worksheets if not ws.title.startswith('_') and achar_calendario(ws)), None)
    if mestre is None:
        raise ValueError('O template não está no modo calendário (precisa de {{DATA}} no cabeçalho e {{VALOR}} na linha dos itens).')
    geo = achar_calendario(mestre)
    ancora, col_ini = geo['ancora'], geo['col_ini']
    turnos = list(Turno.objects.filter(ativo=True))
    celula_data = mestre.cell(row=geo['linha_data'], column=col_ini)
    mescla_data = next((m for m in mestre.merged_cells.ranges if celula_data.coordinate in m), None)
    larg = (mescla_data.max_col - mescla_data.min_col + 1) if mescla_data else max(1, len(turnos))
    dias = [ini + datetime.timedelta(days=n) for n in range((fim - ini).days + 1)]
    if col_ini + len(dias) * larg - 1 > 16384:
        raise ValueError(f'Período grande demais para o Excel: no máximo {(16384 - col_ini + 1) // larg} dias com {larg} coluna(s) por dia.')
    ultima_col = col_ini + len(dias) * larg - 1
    max_linha = mestre.max_row
    tem_2o_bloco = mestre.max_column >= col_ini + 2 * larg - 1    # o 2º bloco é o padrão; o 1º é o que fica junto à parte fixa
    links_mestre = [c for c in mestre._cells.values() if c.hyperlink is not None and c.hyperlink.location and c.column < col_ini]
    nome_indice = 'Índice'
    indice = wb.create_sheet(nome_indice, 0)
    usados = {nome_indice.lower()}
    abas = []

    for pagina in paginas:
        campos = list(pagina.campos.filter(ativo=True).select_related('frequencia').order_by('ordem', 'pk'))
        respostas, parados = lancamentos_da_pagina(formulario, pagina, ini, fim)
        escalares = _escalares(formulario, versao, pagina, ini, fim, dias[:31], campos, hoje)
        ws = wb.create_sheet(_nome_aba(pagina.nome, usados))
        abas.append((pagina, ws.title))
        extra = max(len(campos), 1) - 1
        total_linhas = max_linha + extra

        def linha_origem(r):
            if r <= ancora:
                return r
            return r - extra if r > ancora + extra else ancora

        def coluna_origem(c):
            if c < col_ini:
                return c
            bloco, off = divmod(c - col_ini, larg)
            return col_ini + off + (larg if bloco > 0 and tem_2o_bloco else 0)

        for r in range(1, total_linhas + 1):
            h = mestre.row_dimensions[linha_origem(r)].height
            if h is not None:
                ws.row_dimensions[r].height = h
        larguras = {}
        for c in range(1, ultima_col + 1):
            co = coluna_origem(c)
            if co not in larguras:
                larguras[co] = _largura_coluna(mestre, co)
            if larguras[co]:
                ws.column_dimensions[get_column_letter(c)].width = larguras[co]

        def so_escalares(texto):
            return _substituir(texto, lambda tag, _: escalares[tag] if classificar(tag) in ('escalar', 'dia') else '{{' + tag + '}}')

        fonte_nok = {}
        for r in range(1, total_linhas + 1):
            ro = linha_origem(r)
            e_item = ancora <= r <= ancora + extra
            campo = campos[r - ancora] if e_item and campos else None
            for c in range(1, ultima_col + 1):
                origem = mestre.cell(row=ro, column=coluna_origem(c))
                if not origem.has_style and origem.value is None:
                    continue
                cel = ws.cell(row=r, column=c)
                if origem.has_style:
                    cel._style = copy(origem._style)
                texto = origem.value if isinstance(origem.value, str) else None
                if c < col_ini:                                               # parte fixa: cabeçalho do documento e dados do item
                    if texto is None or '{{' not in texto:
                        cel.value = origem.value
                    elif e_item and ro == ancora:
                        cel.value = _substituir(texto, lambda tag, inteira, campo=campo: _tag_item(tag, campo, escalares))
                    else:
                        cel.value = so_escalares(texto)
                    continue
                bloco, off = divmod(c - col_ini, larg)
                if ro == geo['linha_data']:
                    if off == 0:
                        cel.value = dias[bloco]
                elif geo['linha_turno'] and ro == geo['linha_turno']:
                    if off < len(turnos):
                        cel.value = turnos[off].sigla
                elif ro == ancora:
                    if campo is not None and off < len(turnos):
                        dia, turno = dias[bloco], turnos[off]
                        status = parados.get((dia, turno.pk))
                        if status:
                            cel.value = ROTULOS[status]
                            cel.fill = PatternFill('solid', fgColor=COR_STATUS[status])
                            cel.alignment = Alignment(horizontal='center', vertical='center', shrink_to_fit=True)
                        else:
                            lancado = respostas.get(chave(campo.item, campo.etapa, campo.descricao), {}).get((dia, turno.pk))
                            if lancado:
                                cel.value = _valor_celula(campo, lancado[0])
                                if lancado[1] is False:
                                    if id(origem.font) not in fonte_nok:
                                        f = copy(origem.font)
                                        f.color, f.b = 'C00000', True
                                        fonte_nok[id(origem.font)] = f
                                    cel.font = fonte_nok[id(origem.font)]
                elif texto is not None:
                    cel.value = texto if '{{' not in texto else so_escalares(texto)
        # mesclagens: parte fixa (com as linhas abaixo da âncora deslocadas) e as de cada bloco de data, a partir do bloco-modelo
        for m in mestre.merged_cells.ranges:
            if m.min_col < col_ini:
                d = extra if m.min_row > ancora else 0
                ws.merged_cells.add(CellRange(min_col=m.min_col, min_row=m.min_row + d, max_col=m.max_col, max_row=m.max_row + d))
        for bloco in range(len(dias)):
            base = col_ini + (larg if bloco > 0 and tem_2o_bloco else 0)
            for m in mestre.merged_cells.ranges:
                if base <= m.min_col < base + larg:
                    d = extra if m.min_row > ancora else 0
                    desloc_col = col_ini + bloco * larg - base
                    # direto na lista de mesclagens: as células já herdaram as bordas do template (merge_cells reformatava cada uma)
                    ws.merged_cells.add(CellRange(min_col=m.min_col + desloc_col, min_row=m.min_row + d, max_col=m.max_col + desloc_col, max_row=m.max_row + d))
        # aparência da aba
        ws.freeze_panes = mestre.freeze_panes
        ws.sheet_view.showGridLines = mestre.sheet_view.showGridLines
        ws.sheet_view.zoomScale = mestre.sheet_view.zoomScale
        ws.page_setup.orientation, ws.page_setup.paperSize, ws.page_setup.scale = (
            mestre.page_setup.orientation, mestre.page_setup.paperSize, mestre.page_setup.scale)
        ws.page_margins = copy(mestre.page_margins)
        for dv in mestre.data_validations.dataValidation:
            novo = DataValidation(type=dv.type, operator=dv.operator, formula1=dv.formula1, formula2=dv.formula2, allow_blank=dv.allow_blank,
                                  showErrorMessage=dv.showErrorMessage, showInputMessage=dv.showInputMessage, errorTitle=dv.errorTitle,
                                  error=dv.error, promptTitle=dv.promptTitle, prompt=dv.prompt)
            for faixa in dv.sqref.ranges:
                ult = max(ultima_col if faixa.max_col >= mestre.max_column else faixa.max_col, faixa.min_col)
                r1 = faixa.min_row + (extra if faixa.min_row > ancora else 0)
                r2 = faixa.max_row + (extra if faixa.max_row > ancora else 0)
                novo.add(f'{get_column_letter(faixa.min_col)}{r1}:{get_column_letter(ult)}{r2}')
            ws.add_data_validation(novo)
        for origem in links_mestre:
            ws[origem.coordinate].hyperlink = Hyperlink(ref=origem.coordinate, location=origem.hyperlink.location, display=origem.hyperlink.display)

    # índice: destino do "Voltar ao índice" do template, com um link para cada página
    cab, branco = PatternFill('solid', fgColor='14284B'), Font(bold=True, color='FFFFFF')
    indice['A1'] = f'{formulario.codigo} · {versao.revisao} — Índice'
    indice['A1'].font = Font(bold=True, size=13)
    indice['A2'] = f'Período: {ini:%d/%m/%Y} a {fim:%d/%m/%Y} · extraído em {hoje:%d/%m/%Y}'
    indice['A2'].font = Font(italic=True, color='666666')
    for j, t in enumerate(('Grupo', 'Página'), 1):
        c = indice.cell(row=4, column=j, value=t)
        c.font, c.fill = branco, cab
    for k, (pagina, aba) in enumerate(abas, 5):
        indice.cell(row=k, column=1, value=pagina.grupo)
        c = indice.cell(row=k, column=2, value=pagina.nome)
        c.hyperlink = Hyperlink(ref=c.coordinate, location=f"'{aba}'!A1", display=pagina.nome)
        c.font = Font(color='0563C1', underline='single')
    indice.column_dimensions['A'].width = 28
    indice.column_dimensions['B'].width = 40
    manter = {a for _, a in abas} | {nome_indice}
    for ws in [w for w in wb.worksheets if w.title not in manter]:
        wb.remove(ws)
    wb.active = 0
    saida = BytesIO()
    wb.save(saida)
    saida.seek(0)
    return saida
