from __future__ import annotations

from cybertrust.apps.organizations.models import Membership


def is_admin(membership: Membership | None) -> bool:
    return bool(membership and membership.is_active and membership.role == Membership.ROLE_ADMIN)
