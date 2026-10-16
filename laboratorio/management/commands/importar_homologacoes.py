"""Importa a planilha "Acompanhamento - Plano de Teste" (aba Dados) para os planos de homologação.

Uso: python manage.py importar_homologacoes caminho/da/planilha.xlsm [--dry-run]
"""
from django.core.management.base import BaseCommand, CommandError

from laboratorio.homologacao_import import PlanilhaInvalida, importar_planilha, resumo_texto


class Command(BaseCommand):
    help = "Importa planos de homologação da planilha de acompanhamento (aba Dados)."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--dry-run", action="store_true", help="Só mostra o que seria importado.")

    def handle(self, *args, **opts):
        try:
            relatorio = importar_planilha(opts["arquivo"], dry_run=opts["dry_run"])
        except PlanilhaInvalida as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(resumo_texto(relatorio) + (" (dry-run, nada gravado)" if opts["dry_run"] else "")))
