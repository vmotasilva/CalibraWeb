"""
Módulo para exportação de Matrizes de Habilidades em CSV ou Excel
"""
import csv
import io
from datetime import datetime
from typing import Dict, List, Tuple

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from procedures.models import MatrizHabilidade, Disciplina, ColaboradorMatrizHabilidade


class ExportadorMatrizHabilidade:
    """
    Responsável por exportar dados de Matrizes em CSV ou Excel
    """

    def __init__(self):
        """Inicializa o exportador"""
        self.data_export = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def exportar_csv(self) -> Tuple[io.StringIO, str]:
        """
        Exporta matrizes em formato CSV

        Returns:
            Tuple contendo (StringIO com dados, nome do arquivo)
        """
        output = io.StringIO()
        writer = csv.writer(output, delimiter='|')

        # Header
        writer.writerow([
            'Matriz Código',
            'Matriz Nome',
            'Disciplina Código',
            'Disciplina Nome',
            'Colaborador Matrícula',
            'Colaborador Nome',
            'Nível de Competência',
            'Observações'
        ])

        # Dados - Matriz -> Disciplina -> Colaborador (via AvaliacaoHabilidade)
        for matriz in MatrizHabilidade.objects.prefetch_related(
            'disciplinas_matriz'
        ).all():
            disciplinas = matriz.disciplinas_matriz.all()

            if not disciplinas.exists():
                # Matriz sem disciplinas
                writer.writerow([
                    matriz.codigo,
                    matriz.nome,
                    '', '', '', '', ''
                ])
            else:
                for disciplina in disciplinas:
                    # Buscar colaboradores que têm avaliação nesta disciplina e matriz
                    from procedures.models import AvaliacaoHabilidade
                    avaliacoes = AvaliacaoHabilidade.objects.filter(
                        matriz=matriz,
                        disciplina=disciplina
                    ).select_related('colaborador').order_by('colaborador').distinct()

                    if not avaliacoes.exists():
                        # Disciplina sem colaboradores com avaliação
                        writer.writerow([
                            matriz.codigo,
                            matriz.nome,
                            disciplina.codigo,
                            disciplina.nome,
                            '', '', '', ''
                        ])
                    else:
                        for avaliacao in avaliacoes:
                            colaborador = avaliacao.colaborador
                            writer.writerow([
                                matriz.codigo,
                                matriz.nome,
                                disciplina.codigo,
                                disciplina.nome,
                                colaborador.matricula,
                                colaborador.nome,
                                avaliacao.get_nivel_display() or '',
                                avaliacao.observacoes or ''
                            ])

        filename = f"exportacao_matrizes_{self.timestamp}.csv"
        return output, filename

    def exportar_excel(self) -> Tuple[bytes, str]:
        """
        Exporta matrizes em formato Excel

        Returns:
            Tuple contendo (bytes do arquivo, nome do arquivo)
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Matrizes"

        # Estilos
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # Headers
        headers = [
            'Matriz Código',
            'Matriz Nome',
            'Disciplina Código',
            'Disciplina Nome',
            'Colaborador Matrícula',
            'Colaborador Nome',
            'Nível de Competência',
            'Observações'
        ]

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = border

        # Dados
        from procedures.models import AvaliacaoHabilidade
        row_num = 2
        for matriz in MatrizHabilidade.objects.prefetch_related(
            'disciplinas_matriz'
        ).all():
            disciplinas = matriz.disciplinas_matriz.all()

            if not disciplinas.exists():
                # Matriz sem disciplinas
                ws.cell(row=row_num, column=1).value = matriz.codigo
                ws.cell(row=row_num, column=2).value = matriz.nome
                row_num += 1
            else:
                for disciplina in disciplinas:
                    avaliacoes = AvaliacaoHabilidade.objects.filter(
                        matriz=matriz,
                        disciplina=disciplina
                    ).select_related('colaborador').order_by('colaborador').distinct()

                    if not avaliacoes.exists():
                        # Disciplina sem colaboradores com avaliação
                        ws.cell(row=row_num, column=1).value = matriz.codigo
                        ws.cell(row=row_num, column=2).value = matriz.nome
                        ws.cell(row=row_num, column=3).value = disciplina.codigo
                        ws.cell(row=row_num, column=4).value = disciplina.nome
                        row_num += 1
                    else:
                        for avaliacao in avaliacoes:
                            colaborador = avaliacao.colaborador
                            ws.cell(row=row_num, column=1).value = matriz.codigo
                            ws.cell(row=row_num, column=2).value = matriz.nome
                            ws.cell(row=row_num, column=3).value = disciplina.codigo
                            ws.cell(row=row_num, column=4).value = disciplina.nome
                            ws.cell(row=row_num, column=5).value = colaborador.matricula
                            ws.cell(row=row_num, column=6).value = colaborador.nome
                            ws.cell(row=row_num, column=7).value = avaliacao.get_nivel_display() or ''
                            ws.cell(row=row_num, column=8).value = avaliacao.observacoes or ''

                            # Aplicar border a todas as células
                            for col in range(1, 9):
                                ws.cell(row=row_num, column=col).border = border

                            row_num += 1

        # Ajustar largura das colunas
        column_widths = [15, 25, 15, 25, 18, 25, 20, 40]
        for idx, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        # Congelar primeira linha
        ws.freeze_panes = "A2"

        # Salvar em memória
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"exportacao_matrizes_{self.timestamp}.xlsx"
        return output.getvalue(), filename

    def gerar_relatorio_exportacao(self) -> Dict:
        """
        Gera relatório de dados para exportação

        Returns:
            Dict com estatísticas
        """
        matrizes = MatrizHabilidade.objects.all()
        disciplinas = Disciplina.objects.all()
        colaboradores = ColaboradorMatrizHabilidade.objects.all()

        return {
            'total_matrizes': matrizes.count(),
            'total_disciplinas': disciplinas.count(),
            'total_associacoes': colaboradores.count(),
            'data_export': self.data_export,
            'status': 'Pronto para exportar'
        }
