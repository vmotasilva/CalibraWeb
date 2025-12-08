"""Command: python manage.py importar_pacotes_treinamento

Le JSON em database/pacotes_treinamento_config.json e cria/atualiza PacoteTreinamento
associando procedimentos listados. Nao falha se algum codigo estiver ausente; apenas relata.

Edite livremente o arquivo JSON antes de rodar novamente.
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from rh.models import PacoteTreinamento
from training.models import Procedimento


class Command(BaseCommand):
    help = "Importa/atualiza pacotes de treinamento a partir de um arquivo JSON configuravel"

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            type=str,
            default="database/pacotes_treinamento_config.json",
            help="Caminho para o JSON de pacotes",
        )
        parser.add_argument(
            "--atualizar",
            action="store_true",
            help="Se setado, limpa procedimentos existentes do pacote antes de reaplicar",
        )

    def handle(self, *args, **options):
        path = Path(options["arquivo"]).resolve()
        if not path.exists():
            self.stderr.write(f"Arquivo nao encontrado: {path}")
            return

        self.stdout.write(f"Lendo arquivo de pacotes: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        total_pacotes = 0
        codigos_inexistentes_global = set()

        with transaction.atomic():
            for pacote_cfg in data:
                nome = pacote_cfg.get("nome")
                descricao = pacote_cfg.get("descricao", "")
                codigos = list(dict.fromkeys(pacote_cfg.get("procedimentos", [])))  # remove duplicatas preservando ordem

                if not nome:
                    self.stderr.write("Pacote sem 'nome' ignorado.")
                    continue

                pacote, created = PacoteTreinamento.objects.get_or_create(
                    nome=nome, defaults={"descricao": descricao}
                )
                if not created and options["atualizar"]:
                    pacote.procedimentos.clear()

                if created:
                    self.stdout.write(f"CRIADO pacote: {nome}")
                else:
                    self.stdout.write(f"ATUALIZANDO pacote: {nome}")

                encontrados = 0
                for codigo in codigos:
                    try:
                        proc = Procedimento.objects.get(codigo=codigo)
                        pacote.procedimentos.add(proc)
                        encontrados += 1
                    except Procedimento.DoesNotExist:
                        codigos_inexistentes_global.add(codigo)
                        self.stdout.write(f"  Aviso: procedimento nao encontrado: {codigo}")

                pacote.descricao = descricao[:500]
                pacote.save()
                total_pacotes += 1
                self.stdout.write(
                    f"Resumo pacote '{nome}': {encontrados}/{len(codigos)} procedimentos associados"
                )

        self.stdout.write("\n==== RELATORIO FINAL ====")
        self.stdout.write(f"Pacotes processados: {total_pacotes}")
        if codigos_inexistentes_global:
            self.stdout.write(
                f"Codigos inexistentes totais ({len(codigos_inexistentes_global)}): "
                + ", ".join(sorted(codigos_inexistentes_global))
            )
        else:
            self.stdout.write("Todos os codigos foram encontrados.")
        self.stdout.write("Importacao de pacotes concluida.")
