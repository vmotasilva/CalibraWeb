import datetime
import glob
import os

from django.core.management.base import BaseCommand, CommandError

from pcp import importacao_diaria


class Command(BaseCommand):
    help = ('Importação diária do PCP: lê as planilhas em uso (uma pasta ou vários arquivos .xlsx), grava só os lançamentos '
            'nas páginas já existentes e mostra o que ficou sem preenchimento. Não altera a estrutura dos formulários.')

    def add_arguments(self, parser):
        parser.add_argument('caminhos', nargs='+', help='Arquivos .xlsx e/ou pastas com planilhas FOR.xxx.Rxx.')
        parser.add_argument('--dias', type=int, default=importacao_diaria.DIAS_JANELA_PADRAO,
                            help='Reimporta os últimos N dias (padrão: %(default)s).')
        parser.add_argument('--desde', help='Primeira data reimportada (AAAA-MM-DD); substitui --dias.')
        parser.add_argument('--ano-todo', action='store_true', help='Reimporta o ano inteiro.')
        parser.add_argument('--nao-atualizar', action='store_true', help='Não atualiza valores já gravados que mudaram na planilha.')
        parser.add_argument('--simular', action='store_true', help='Mostra o que seria importado sem gravar nada.')

    def handle(self, *args, **o):
        hoje = datetime.date.today()
        if o['ano_todo']:
            desde = datetime.date(hoje.year, 1, 1)
        elif o['desde']:
            try:
                desde = datetime.date.fromisoformat(o['desde'])
            except ValueError:
                raise CommandError('--desde deve estar no formato AAAA-MM-DD.')
        else:
            desde = hoje - datetime.timedelta(days=o['dias'])
        arquivos = []
        for c in o['caminhos']:
            arquivos += sorted(glob.glob(os.path.join(c, '*.xlsx'))) if os.path.isdir(c) else [c]
        arquivos = [a for a in arquivos if not os.path.basename(a).startswith('~$')]  # temporários do Excel
        if not arquivos:
            raise CommandError('Nenhuma planilha .xlsx encontrada.')
        w = self.stdout.write
        falhas = 0
        for caminho in arquivos:
            w(self.style.MIGRATE_HEADING(os.path.basename(caminho)))
            try:
                r, av = importacao_diaria.importar_diario(caminho, ano=desde.year, desde=desde, atualizar=not o['nao_atualizar'],
                                                          simular=o['simular'], hoje=hoje)
            except (ValueError, OSError) as e:
                falhas += 1
                w(self.style.ERROR(f'  {e}'))
                continue
            titulo = 'SIMULAÇÃO' if r['simulado'] else 'Importado'
            w(self.style.SUCCESS(f"  {titulo} em {r['versao']} (a partir de {desde:%d/%m/%Y}): {r['respostas_novas']} novos, "
                                 f"{r['respostas_atualizadas']} atualizados, {r['respostas_existentes']} já existiam, {r['fora_do_limite']} fora do limite."))
            for aba in r['sem_pagina']:
                w(self.style.WARNING(f'  aba sem página na revisão {r["versao"]}: {aba}'))
            if r['linhas_sem_item']:
                w(self.style.WARNING(f"  {r['linhas_sem_item']} linhas da planilha sem item correspondente (estrutura diferente?)"))
            if r['nao_reconhecidos']:
                w(self.style.WARNING(f"  {len(r['nao_reconhecidos'])} valores fora das opções da lista (gravados sem conformidade)"))
            if av and av['devidos']:
                w(f"  Preenchimento {av['desde']:%d/%m} a {av['ate']:%d/%m}: {av['feitos']} de {av['devidos']} ({av['pct']}%), "
                  f"{av['pendentes']} sem preenchimento em {len(av['paginas_com_pendencia'])} página(s)")
                for p in av['paginas_com_pendencia'][:10]:
                    w(f"    {p['nome']}: {p['atrasados']} sem preenchimento ({p['pct']}%)")
        if falhas:
            raise CommandError(f'{falhas} planilha(s) com erro.')
