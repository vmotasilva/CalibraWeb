"""
Management command: deduplicate_perguntas
Deduplicates BancoPergunta records that share the same texto_pergunta (normalized).
Keeps the oldest record (lowest id) as the canonical one and:
  - migrates M2M: AgendaAuditoriaIso.perguntas, BlocoModeloIso.perguntas, ModeloAuditoriaIso.perguntas
  - migrates FK: RespostaEntrevistaIso.pergunta, SolicitacaoEvidenciaIso.pergunta
  - merges itens_norma M2M into the canonical record
  - deletes the duplicate records
"""

import unicodedata
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction


def normalize_text(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


class Command(BaseCommand):
    help = "Deduplica perguntas do BancoPergunta ISO com mesmo texto, unificando vinculos e removendo duplicatas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Apenas reporta duplicatas sem modificar o banco.",
        )

    def handle(self, *args, **options):
        from auditoria.models import (
            BancoPergunta,
            AgendaAuditoriaIso,
            BlocoModeloIso,
            ModeloAuditoriaIso,
            RespostaEntrevistaIso,
            SolicitacaoEvidenciaIso,
        )

        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== MODO DRY-RUN: nenhuma alteracao sera feita ===\n"))
        else:
            self.stdout.write(self.style.WARNING("=== INICIANDO DEDUPLICACAO DE PERGUNTAS ===\n"))

        todas = BancoPergunta.objects.all().order_by("id")
        grupos = defaultdict(list)
        for p in todas:
            chave = normalize_text(p.texto_pergunta)
            grupos[chave].append(p)

        duplicados_encontrados = {k: v for k, v in grupos.items() if len(v) > 1}
        total_grupos = len(duplicados_encontrados)
        total_duplicatas = sum(len(v) - 1 for v in duplicados_encontrados.values())

        self.stdout.write(f"Grupos com duplicatas: {total_grupos}")
        self.stdout.write(f"Registros a remover: {total_duplicatas}\n")

        if total_grupos == 0:
            self.stdout.write(self.style.SUCCESS("Nenhuma duplicata encontrada. Banco ja esta limpo!"))
            return

        removidos = 0
        migrados_resp = 0
        migrados_sol = 0
        migrados_agenda = 0
        migrados_bloco = 0
        migrados_modelo = 0

        for chave, grupo in duplicados_encontrados.items():
            canonico = grupo[0]
            duplicatas = grupo[1:]

            self.stdout.write(f"\nCanonica: #{canonico.id} | \"{canonico.texto_pergunta[:70]}\"")
            self.stdout.write(f"  Duplicatas: {[d.id for d in duplicatas]}")

            if dry_run:
                for dup in duplicatas:
                    resp_count = RespostaEntrevistaIso.objects.filter(pergunta=dup).count()
                    sol_count = SolicitacaoEvidenciaIso.objects.filter(pergunta=dup).count()
                    ag_count = AgendaAuditoriaIso.objects.filter(perguntas=dup).count()
                    bl_count = BlocoModeloIso.objects.filter(perguntas=dup).count()
                    mo_count = ModeloAuditoriaIso.objects.filter(perguntas=dup).count()
                    self.stdout.write(
                        f"  -> #{dup.id}: respostas={resp_count}, solicitacoes={sol_count}, "
                        f"agendas={ag_count}, blocos={bl_count}, modelos={mo_count}"
                    )
                continue

            with transaction.atomic():
                for dup in duplicatas:
                    itens_dup = list(dup.itens_norma.all())
                    if itens_dup:
                        canonico.itens_norma.add(*itens_dup)

                    for resp in RespostaEntrevistaIso.objects.filter(pergunta=dup):
                        existe = RespostaEntrevistaIso.objects.filter(
                            auditoria=resp.auditoria,
                            pergunta=canonico
                        ).exists()
                        if not existe:
                            resp.pergunta = canonico
                            resp.save(update_fields=["pergunta"])
                            migrados_resp += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Descartando resposta #{resp.id} (auditoria={resp.auditoria_id})"
                                    " - canonica ja possui resposta para esta auditoria."
                                )
                            )
                            resp.delete()

                    sol_qs = SolicitacaoEvidenciaIso.objects.filter(pergunta=dup)
                    count_sol = sol_qs.count()
                    if count_sol:
                        sol_qs.update(pergunta=canonico)
                        migrados_sol += count_sol

                    for agenda in AgendaAuditoriaIso.objects.filter(perguntas=dup):
                        agenda.perguntas.remove(dup)
                        agenda.perguntas.add(canonico)
                        migrados_agenda += 1

                    for bloco in BlocoModeloIso.objects.filter(perguntas=dup):
                        bloco.perguntas.remove(dup)
                        bloco.perguntas.add(canonico)
                        migrados_bloco += 1

                    for modelo in ModeloAuditoriaIso.objects.filter(perguntas=dup):
                        modelo.perguntas.remove(dup)
                        modelo.perguntas.add(canonico)
                        migrados_modelo += 1

                    self.stdout.write(f"  Removendo BancoPergunta #{dup.id}")
                    dup.delete()
                    removidos += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nDEDUPLICACAO CONCLUIDA:"
                f"\n  Grupos: {total_grupos}"
                f"\n  Removidas: {removidos}"
                f"\n  Respostas migradas: {migrados_resp}"
                f"\n  Solicitacoes migradas: {migrados_sol}"
                f"\n  Agendas ajustadas: {migrados_agenda}"
                f"\n  Blocos ajustados: {migrados_bloco}"
                f"\n  Modelos ajustados: {migrados_modelo}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nDry-run: {total_grupos} grupos, {total_duplicatas} duplicatas detectadas."
            ))
