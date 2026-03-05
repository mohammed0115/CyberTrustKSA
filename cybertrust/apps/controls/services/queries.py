from __future__ import annotations

from django.db.models import QuerySet

from cybertrust.apps.controls.models import Control, ControlCategory


def get_control(control_id: int) -> Control | None:
    return Control.objects.filter(id=control_id, is_active=True).select_related("category").first()


def list_controls() -> QuerySet[Control]:
    return Control.objects.filter(is_active=True).select_related("category")


def list_categories() -> QuerySet[ControlCategory]:
    return ControlCategory.objects.all().order_by("order", "name_en")
