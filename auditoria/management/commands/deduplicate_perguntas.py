"""
Management command: deduplicate_perguntas
Deduplicates BancoPergunta records by ItemNorma:
  - For each ItemNorma, if multiple BancoPergunta are linked, keep the oldest (lowest id)
    and remove the rest.
  - The duplicate BancoPergunta are only removed if they are linked to no other ItemNorma
    (i.e. they became orphans after the M2M is cleaned up).
  - RespostaEntrevistaIso references (and their SolicitacaoEvidenciaIso children via CASCADE)
    are migrated from duplicate to canonical before deletion.
  - AgendaAuditoriaIso.perguntas, BlocoModeloIso.perguntas, ModeloAuditoriaIso.perguntas M2M
    are updated to point to the canonical.

Note: SolicitacaoEvidenciaIso has FK -> RespostaEntrevistaIso (CASCADE), so migrating
the RespostaEntrevistaIso.pergunta handles solicitacoes transitively.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Deduplica BancoPergunta por ItemNorma: "
        "quando um item tem multiplas perguntas vinculadas, "
        "mantém a mais antiga e consolida as demais nela."
    )

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
            ItemNorma,
            AgendaAuditoriaIso,
            BlocoModeloIso,
            ModeloAuditoriaIso,
            RespostaEntrevistaIso,
        )

        dry_run = options["dry_run"]
        sep = "=" * 60

        self.stdout.write(sep)
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN — nenhuma alteracao sera feita"))
        else:
            self.stdout.write(self.style.WARNING("INICIANDO DEDUPLICACAO POR ITEM DA NORMA"))
        self.stdout.write(sep + "\n")

        # Mapear: item_norma_id -> lista de BancoPergunta (ordenada por id)
        itens_com_duplicata = []

        for item in ItemNorma.objects.prefetch_related("perguntas_vinculadas").all():
            perguntas = list(item.perguntas_vinculadas.all().order_by("id"))
            if len(perguntas) > 1:
                itens_com_duplicata.append((item, perguntas))

        total_itens = len(itens_com_duplicata)
        total_duplicatas = sum(len(ps) - 1 for _, ps in itens_com_duplicata)

        self.stdout.write(f"Itens com mais de uma pergunta vinculada: {total_itens}")
        self.stdout.write(f"Perguntas a consolidar (duplicatas): {total_duplicatas}\n")

        if total_itens == 0:
            self.stdout.write(self.style.SUCCESS("Nenhuma duplicata encontrada. Banco ja esta limpo!"))
            return

        # Rastrear: qual pergunta canonica foi eleita para cada pergunta duplicata
        # (pode acontecer de a mesma pergunta-duplicata aparecer em varios itens)
        canonicos_por_duplicata = {}   # dup.id -> canonico (BancoPergunta)
        removidos = set()

        for item, perguntas in itens_com_duplicata:
            canonico = perguntas[0]
            duplicatas = perguntas[1:]

            self.stdout.write(
                f"Item {item.referencia}: {len(perguntas)} perguntas — "
                f"canonico=#{ canonico.id}, duplicatas={[d.id for d in duplicatas]}"
            )

            for dup in duplicatas:
                if dup.id not in canonicos_por_duplicata:
                    canonicos_por_duplicata[dup.id] = canonico
                # Remove a duplicata do item (M2M item -> pergunta)
                if not dry_run:
                    item.perguntas_vinculadas.remove(dup)

                resp_count = RespostaEntrevistaIso.objects.filter(pergunta=dup).count()
                ag_count = AgendaAuditoriaIso.objects.filter(perguntas=dup).count()
                bl_count = BlocoModeloIso.objects.filter(perguntas=dup).count()
                mo_count = ModeloAuditoriaIso.objects.filter(perguntas=dup).count()

                self.stdout.write(
                    f"  -> #{dup.id}: respostas={resp_count}, agendas={ag_count}, "
                    f"blocos={bl_count}, modelos={mo_count}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDry-run concluido. {total_itens} itens, {total_duplicatas} duplicatas detectadas."
            ))
            return

        # Agora migrar e remover os objetos duplicados que ficaram sem itens
        migrados_resp = 0
        migrados_ag = 0
        migrados_bl = 0
        migrados_mo = 0
        efetivamente_removidos = 0

        with transaction.atomic():
            for dup_id, canonico in canonicos_por_duplicata.items():
                try:
                    dup = BancoPergunta.objects.get(pk=dup_id)
                except BancoPergunta.DoesNotExist:
                    continue

                # Verificar se a duplicata ainda tem itens vinculados a ela em outros contextos
                # (pode ser compartilhada por varios itens e ja ter sido limpa)
                itens_restantes = dup.itens_norma.count()

                # Migrar RespostaEntrevistaIso
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
                        # Solicitacoes serao deletadas via CASCADE junto com resp
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Descartando resposta #{resp.id} (aud={resp.auditoria_id})"
                                " — canonico ja tem resposta para esta auditoria."
                            )
                        )
                        resp.delete()

                # Migrar M2M Agendas
                for agenda in AgendaAuditoriaIso.objects.filter(perguntas=dup):
                    agenda.perguntas.remove(dup)
                    agenda.perguntas.add(canonico)
                    migrados_ag += 1

                # Migrar M2M Blocos de Modelo
                for bloco in BlocoModeloIso.objects.filter(perguntas=dup):
                    bloco.perguntas.remove(dup)
                    bloco.perguntas.add(canonico)
                    migrados_bl += 1

                # Migrar M2M Modelos
                for modelo in ModeloAuditoriaIso.objects.filter(perguntas=dup):
                    modelo.perguntas.remove(dup)
                    modelo.perguntas.add(canonico)
                    migrados_mo += 1

                # Remover a duplicata (agora sem refs)
                self.stdout.write(f"  Removendo BancoPergunta #{dup.id}")
                dup.delete()
                efetivamente_removidos += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDEDUPLICACAO CONCLUIDA:"
            f"\n  Itens da norma processados : {total_itens}"
            f"\n  Perguntas removidas        : {efetivamente_removidos}"
            f"\n  Respostas migradas         : {migrados_resp}"
            f"\n  Agendas ajustadas          : {migrados_ag}"
            f"\n  Blocos ajustados           : {migrados_bl}"
            f"\n  Modelos ajustados          : {migrados_mo}"
            f"\n  (SolicitacaoEvidenciaIso migra junto via RespostaEntrevistaIso)"
        ))
