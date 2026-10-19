"""Importa a aba "Respostas" da planilha de Rendimento HC (mapeamento automático por nome de coluna).

Uso: python manage.py importar_rendimento_hc "Rendimento HC - TEC - 2025.xlsx" [--aba Respostas] [--dry-run]

Para escolher manualmente a relação coluna -> campo, use a tela HMC > HC > Importar Planilha.
Idempotente: reexecutar não duplica (chave por Id do Forms ou hash da linha).
"""
from django.core.management.base import BaseCommand, CommandError

from laboratorio import hc_importacao as imp


class Command(BaseCommand):
    help = "Importa a aba 'Respostas' da planilha de Rendimento HC."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--aba", default=None)
        parser.add_argument("--dry-run", action="store_true", help="Só valida e mostra o resumo; não grava.")

    def handle(self, *args, arquivo, aba=None, dry_run=False, **opts):
        try:
            with open(arquivo, "rb") as f:
                dados = imp.ler_planilha(f, aba)
            r = imp.importar(dados["linhas"], imp.sugerir_mapa(dados["cabecalhos"]), simular=dry_run)
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc))
        self.stdout.write(
            f"Linhas válidas: {r['validas']} | repetidas/já importadas: {r['repetidas']} | ignoradas (data inválida): {r['ignoradas']} | "
            f"com colaborador vinculado ao RH: {r['com_colaborador']} | a revisar (lentes = 0 ou retrabalho > lentes): {r['a_revisar']}"
        )
        if r["turno_sem_regra"]:
            self.stdout.write(self.style.WARNING(f"Turnos sem regra cadastrada: {r['turno_sem_regra']}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: nada foi gravado."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Importados {r['importadas']} lançamentos."))
