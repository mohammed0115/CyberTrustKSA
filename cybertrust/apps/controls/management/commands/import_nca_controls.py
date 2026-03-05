import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cybertrust.apps.audits.services import record_event
from cybertrust.apps.controls.models import Control, ControlCategory


class Command(BaseCommand):
    help = "Import NCA controls from seed JSON file (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            default=str(Path("cybertrust/apps/controls/data/nca_controls_seed.json")),
            help="Path to NCA controls seed CSV or JSON file.",
        )

    def handle(self, *args, **options):
        path = Path(options["source"])
        if not path.exists():
            raise CommandError(f"Seed file not found: {path}")

        if path.suffix.lower() == ".csv":
            data = []
            with path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise CommandError("Seed file must contain a list of controls.")

        created = 0
        updated = 0
        category_map = {}

        with transaction.atomic():
            for idx, item in enumerate(data, start=1):
                category_en = item.get("category_en", "").strip()
                category_ar = item.get("category_ar", "").strip()
                category_code = item.get("category_code", "").strip()
                if not category_en:
                    raise CommandError(f"Missing category_en at item {idx}")

                category = category_map.get(category_en)
                if not category:
                    category, _ = ControlCategory.objects.get_or_create(
                        name_en=category_en,
                        defaults={
                            "name_ar": category_ar or category_en,
                            "order": len(category_map) + 1,
                            "code": category_code or "",
                        },
                    )
                    category_map[category_en] = category
                if category_ar and category.name_ar != category_ar:
                    category.name_ar = category_ar
                if category_code and category.code != category_code:
                    category.code = category_code
                category.order = category.order or len(category_map)
                category.save(update_fields=["name_ar", "code", "order"])

                defaults = {
                    "category": category,
                    "title_ar": item.get("title_ar", "").strip(),
                    "title_en": item.get("title_en", "").strip(),
                    "description_ar": item.get("description_ar", "").strip() or None,
                    "description_en": item.get("description_en", "").strip() or None,
                    "risk_level": item.get("risk_level", Control.RISK_MEDIUM),
                    "required_evidence": item.get("required_evidence", "").strip(),
                    "references": item.get("references"),
                    "is_active": True,
                }
                control, was_created = Control.objects.update_or_create(code=item["code"], defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1

        record_event(
            "controls.import",
            message=f"Imported NCA controls ({created} created, {updated} updated).",
            metadata={"created": created, "updated": updated},
        )
        self.stdout.write(self.style.SUCCESS(f"Imported controls. Created: {created}, Updated: {updated}"))
