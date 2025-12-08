import unicodedata
from typing import Any, Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from metrologia.models import CategoriaInstrumento, Instrumento


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.upper()


def _variants(name: str) -> List[str]:
    n = _norm(name).strip()
    # Basic variants: self, without trailing 'S' (singular), without trailing 'OS'/'AS'
    cand = {n}
    if n.endswith("S"):
        cand.add(n[:-1])
    if n.endswith("OS"):
        cand.add(n[:-2] + "O")
    if n.endswith("AS"):
        cand.add(n[:-2] + "A")
    # Common replacements
    cand.add(n.replace("QUÍ", "QUI"))
    cand.add(n.replace("Ô", "O").replace("Ó", "O"))
    return sorted({c for c in cand if c})


class Command(BaseCommand):
    help = (
        "Infer and set Instrumento.categoria by matching CategoriaInstrumento.nome "
        "against instrument description/fabricante/modelo."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reassign category even if instrument already has one",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would change without saving",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        force = bool(opts.get("force"))
        dry = bool(opts.get("dry_run"))

        cats = list(CategoriaInstrumento.objects.all())
        if not cats:
            self.stdout.write(self.style.WARNING("No categories found."))
            return

        # Build index of patterns
        patterns: List[Tuple[CategoriaInstrumento, List[str]]] = []
        for c in cats:
            pats = _variants(c.nome)
            patterns.append((c, pats))

        assigned = 0
        skipped = 0
        examined = 0
        changes_preview: List[Tuple[int, str, str]] = []

        with transaction.atomic():
            for inst in Instrumento.objects.all():
                examined += 1
                if inst.categoria_id and not force:
                    skipped += 1
                    continue
                haystack = _norm(" ".join([
                    inst.descricao or "",
                    inst.fabricante or "",
                    inst.modelo or "",
                ]))
                hit = None
                for cat, pats in patterns:
                    if any(p and p in haystack for p in pats):
                        hit = cat
                        break
                if not hit:
                    continue
                if dry:
                    changes_preview.append((inst.id, inst.tag, hit.nome))
                else:
                    inst.categoria = hit
                    inst.save(update_fields=["categoria"])
                    assigned += 1
            if dry:
                # Rollback preview changes
                transaction.set_rollback(True)

        if dry:
            self.stdout.write(self.style.WARNING("Dry-run: no changes saved"))
            self.stdout.write(f"Would assign {len(changes_preview)} instruments:")
            for iid, tag, catname in changes_preview[:50]:
                self.stdout.write(f" - {tag} -> {catname} (id={iid})")
            if len(changes_preview) > 50:
                self.stdout.write(f" ... and {len(changes_preview)-50} more")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Examined: {examined} | Assigned: {assigned} | Skipped (kept existing): {skipped}"
                )
            )
