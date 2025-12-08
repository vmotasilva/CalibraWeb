import json
import os
from typing import Any, List, Tuple, cast
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
from metrologia.models import Instrumento, CategoriaInstrumento

"""
Usage:
  python manage.py apply_category_mapping [path_to_json]

Purpose:
  - Create/update CategoriaInstrumento entries based on a simple mapping
  - Assign instruments to categories inferred from their description/model/fabricante

Mapping file format (JSON):
{
  "rules": [
    { "categoria": "PAQUÍMETROS", "contains_any": ["PAQUIMETRO", "PAQUÍMETRO"] },
    { "categoria": "MICRÔMETROS", "contains_any": ["MICROMETRO", "MICRÔMETRO"] },
    { "categoria": "TORQUÍMETROS", "contains_any": ["TORQUIMETRO", "TORQUÍMETRO", "TORQUE"] }
  ]
}

How it works:
  - For instruments without a category, we scan the uppercase concatenation of
    description, fabricante and modelo for any of the substrings in contains_any.
  - On first match, we assign the corresponding category (creating it if missing).
  - If an instrument already has a category, we skip it by default (unless --force).
"""

class Command(BaseCommand):
    help = "Apply category mapping to instruments using a JSON rules file"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "json_path",
            nargs="?",
            default=None,
            help="Path to JSON mapping file. Defaults to database/categorias_map.json",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reassign category even if instrument already has one",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        json_path = options.get("json_path")
        force = options.get("force", False)

        if not json_path:
            json_path = os.path.join(settings.BASE_DIR, "database", "categorias_map.json")
        if not os.path.exists(json_path):
            raise CommandError(f"Mapping file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules", [])
        if not rules:
            raise CommandError("No rules found in mapping file (expected key 'rules').")

        # Normalize rules
        norm_rules: List[Tuple[str, List[str]]] = []
        for r in rules:
            cat = (r.get("categoria") or "").strip()
            raw_list: List[Any] = cast(List[Any], r.get("contains_any") or [])
            pats: List[str] = [str(p).strip().upper() for p in raw_list if str(p).strip()]
            if not cat or not pats:
                continue
            norm_rules.append((cat, pats))

        if not norm_rules:
            raise CommandError("No valid rules after normalization.")

        created_cats = 0
        assigned = 0
        skipped = 0

        with transaction.atomic():
            # Ensure categories exist
            for cat_name, _ in norm_rules:
                _, created = CategoriaInstrumento.objects.get_or_create(nome=cat_name)
                if created:
                    created_cats += 1

            qs = Instrumento.objects.all()
            for inst in qs:
                if inst.categoria and not force:
                    skipped += 1
                    continue
                haystack = " ".join([
                    (inst.descricao or ""),
                    (inst.fabricante or ""),
                    (inst.modelo or ""),
                ]).upper()
                hit = None
                for cat_name, pats in norm_rules:
                    if any(p in haystack for p in pats):
                        hit = cat_name
                        break
                if not hit:
                    continue
                cat = CategoriaInstrumento.objects.get(nome=hit)
                inst.categoria = cat
                inst.save(update_fields=["categoria"])
                assigned += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Categories created: {created_cats} | Instruments assigned: {assigned} | Skipped: {skipped}"
            )
        )
