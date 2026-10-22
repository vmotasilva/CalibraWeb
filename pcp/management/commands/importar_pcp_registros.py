from django.core.management.base import BaseCommand, CommandError

from pcp.importacao_registros import importar_registros
from pcp.models import Formulario


class Command(BaseCommand):
    help = ('Importa os registros (lançamentos por data e turno) de uma planilha de PCP para páginas já importadas. '
            'Separado da importação da estrutura: rode antes o importar_pcp.')

    def add_arguments(self, parser):
        parser.add_argument('arquivo')
        parser.add_argument('--ano', type=int, default=2026, help='Só as colunas desse ano (padrão: 2026).')
        parser.add_argument('--formulario', help='Código do formulário (padrão: lido do nome do arquivo, ex.: FOR.080).')
        parser.add_argument('--revisao', help='Revisão que recebe os registros (padrão: a do nome do arquivo ou a vigente).')
        parser.add_argument('--simular', action='store_true', help='Mostra o que seria importado sem gravar nada.')
        parser.add_argument('--ajustar-tipos', action='store_true',
                            help='Itens de lista cujos lançamentos são quase todos numéricos passam a ser numéricos.')
        parser.add_argument('--rastreio-desde-primeiro-registro', action='store_true',
                            help='Recua a vigência do formulário até o primeiro registro importado, para os atrasos contarem desde então.')

    def handle(self, *args, **o):
        formulario = None
        if o['formulario']:
            formulario = Formulario.objects.filter(codigo=o['formulario'].upper()).first()
            if not formulario:
                raise CommandError(f"Formulário {o['formulario']} não encontrado.")
        try:
            r = importar_registros(o['arquivo'], ano=o['ano'], formulario=formulario, revisao=o['revisao'], simular=o['simular'],
                                   rastreio_desde_primeiro=o['rastreio_desde_primeiro_registro'],
                                   ajustar_tipos=o['ajustar_tipos'])
        except (ValueError, OSError) as e:
            raise CommandError(str(e))
        w = self.stdout.write
        for aba, pagina, n, colunas in r['abas']:
            w(f'  {pagina}: {n} lançamentos ({colunas} colunas de data)')
        for aba in r['sem_pagina']:
            w(self.style.WARNING(f'  aba sem página na revisão {r["versao"]} (importe a estrutura): {aba}'))
        for aba, motivo in r['ignoradas']:
            w(self.style.WARNING(f'  ignorada: {aba} - {motivo}'))
        if r['ocultas']:
            w(f"  abas ocultas desconsideradas: {', '.join(r['ocultas'])}")
        if r['linhas_sem_item']:
            w(self.style.WARNING(f"  {r['linhas_sem_item']} linhas da planilha sem item correspondente na revisão (estrutura diferente?)"))
        for pagina, item, n in r['tipos_ajustados']:
            w(f"  tipo ajustado para número: {pagina} / {item} ({n} lançamentos)")
        if r['futuros']:
            w(self.style.WARNING(f"  {r['futuros']} lançamentos com data futura foram ignorados."))
        for lista, valor, n in r['nao_reconhecidos']:
            w(self.style.WARNING(f"  valor não reconhecido na lista '{lista}': {valor!r} ({n}x) - gravado sem conformidade"))
        periodo = f"{r['primeira_data']:%d/%m/%Y} a {r['ultima_data']:%d/%m/%Y}" if r['primeira_data'] else 'sem dados'
        titulo = 'SIMULAÇÃO (nada foi gravado)' if r['simulado'] else 'Importado'
        w(self.style.SUCCESS(
            f"{titulo} em {r['versao']} ({periodo}): {r['verificacoes_novas']} verificações, {r['respostas_novas']} respostas novas, "
            f"{r['respostas_existentes']} já existiam, {r['fora_do_limite']} fora do limite."))
        if r['vigencia_ajustada']:
            w(f"  Vigência recuada para {r['vigencia_ajustada']:%d/%m/%Y}: os atrasos passam a contar desde essa data.")
