from __future__ import annotations

from typing import Optional

from django.db.models import QuerySet
from django.utils import timezone

from cybertrust.apps.organizations.models import Invitation, Membership, Organization


def get_membership(user, org: Organization) -> Optional[Membership]:
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return Membership.objects.filter(user=user, organization=org, is_active=True).first()


def list_user_memberships(user) -> QuerySet[Membership]:
    if not user or not getattr(user, "is_authenticated", False):
        return Membership.objects.none()
    return (
        Membership.objects.select_related("organization")
        .filter(user=user, is_active=True, organization__is_active=True)
        .order_by("organization__name")
    )


def get_current_org_for_user(user, org_id: Optional[str] = None) -> Optional[Organization]:
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if org_id:
        org = Organization.objects.filter(id=org_id, is_active=True).first()
        if org and get_membership(user, org):
            return org
    membership = list_user_memberships(user).first()
    if membership:
        return membership.organization
    return None


def get_org_by_id(org_id: str | int | None) -> Optional[Organization]:
    if not org_id:
        return None
    return Organization.objects.filter(id=org_id, is_active=True).first()


def get_org_by_slug(slug: str) -> Optional[Organization]:
    return Organization.objects.filter(slug=slug, is_active=True).first()


def list_org_members(org: Organization) -> QuerySet[Membership]:
    return Membership.objects.select_related("user").filter(organization=org).order_by("-is_active", "user__email")


def list_org_invites(org: Organization) -> QuerySet[Invitation]:
    return Invitation.objects.filter(organization=org).order_by("-created_at")


def get_invitation_by_token(token) -> Optional[Invitation]:
    if not token:
        return None
    return Invitation.objects.filter(token=token).first()


def split_invites(invites: QuerySet[Invitation], now=None) -> tuple[QuerySet[Invitation], QuerySet[Invitation], QuerySet[Invitation]]:
    if now is None:
        now = timezone.now()
    active = invites.filter(accepted_at__isnull=True, expires_at__gt=now)
    expired = invites.filter(accepted_at__isnull=True, expires_at__lte=now)
    accepted = invites.filter(accepted_at__isnull=False)
    return active, expired, accepted
