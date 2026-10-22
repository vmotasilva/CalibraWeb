from django.core.management.base import BaseCommand, CommandError

from pcp.importacao import importar_planilha, setor_por_nome


class Command(BaseCommand):
    help = 'Importa a estrutura de um formulário de PCP (.xlsx) como nova revisão (rascunho por padrão).'

    def add_arguments(self, parser):
        parser.add_argument('arquivo')
        parser.add_argument('--setor', required=True, help='Nome do setor (ex.: Surfaçagem). Criado se não existir.')
        parser.add_argument('--codigo', help='Código do formulário (padrão: do nome do arquivo, ex.: FOR.080).')
        parser.add_argument('--revisao', help='Revisão (padrão: do nome do arquivo, ex.: R15).')
        parser.add_argument('--titulo')
        parser.add_argument('--publicar', action='store_true', help='Já publica a revisão como vigente.')
        parser.add_argument('--substituir', action='store_true', help='Recria a revisão se já existir em rascunho.')

    def handle(self, *args, **o):
        try:
            r = importar_planilha(
                o['arquivo'], setor=setor_por_nome(o['setor']), codigo=o['codigo'], revisao=o['revisao'], titulo=o['titulo'],
                publicar=o['publicar'], substituir=o['substituir'])
        except (ValueError, OSError) as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(
            f"{r['versao']} importada ({r['versao'].get_status_display()}): {len(r['paginas'])} páginas, "
            f"{r['total_campos']} campos, {r['frequencias_criadas']} frequências novas."))
        for nome, grupo, layout, n in r['paginas']:
            self.stdout.write(f'  [{grupo or "-"}] {nome} ({layout}): {n}')
        for aba, motivo in r['ignoradas']:
            self.stdout.write(self.style.WARNING(f'  ignorada: {aba} - {motivo}'))
