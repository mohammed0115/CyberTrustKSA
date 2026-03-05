from __future__ import annotations

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from cybertrust.apps.audits.services import record_event
from cybertrust.apps.organizations.models import Invitation, Membership, Organization

from .errors import PermissionDenied, ValidationError
from .policies import is_admin
from .queries import get_membership

User = get_user_model()


def _ensure_unique_slug(base: str) -> str:
    slug = slugify(base)[:50].strip("-")
    if not slug:
        slug = f"org-{uuid4().hex[:8]}"
    candidate = slug
    i = 1
    while Organization.objects.filter(slug=candidate).exists():
        i += 1
        candidate = f"{slug}-{i}"
    return candidate


def _validate_role(role: str) -> str:
    valid_roles = {c[0] for c in Membership.ROLE_CHOICES}
    if role not in valid_roles:
        raise ValidationError("Invalid role.")
    return role


def _ensure_admin(acting_user, org: Organization) -> Membership:
    membership = get_membership(acting_user, org)
    if not is_admin(membership):
        raise PermissionDenied("Admin access required.")
    return membership


def create_organization(user, name: str, industry: str = "", size: str = "") -> Organization:
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    name = (name or "").strip()
    if not name:
        raise ValidationError("Organization name is required.")
    industry = (industry or "").strip()
    size = (size or "").strip()

    slug = _ensure_unique_slug(name)
    with transaction.atomic():
        org = Organization.objects.create(
            name=name,
            slug=slug,
            industry=industry,
            size=size,
            is_active=True,
        )
        Membership.objects.create(user=user, organization=org, role=Membership.ROLE_ADMIN, is_active=True)
    record_event(
        "organization.created",
        organization=org,
        actor=user,
        message=f"Organization created ({org.name}).",
        metadata={"organization_id": org.id},
    )
    return org


def update_organization_settings(
    org: Organization,
    name: str,
    industry: str = "",
    size: str = "",
    acting_user=None,
) -> Organization:
    if acting_user is not None:
        _ensure_admin(acting_user, org)

    name = (name or "").strip()
    if not name:
        raise ValidationError("Organization name is required.")
    org.name = name
    org.industry = (industry or "").strip()
    org.size = (size or "").strip()
    org.save(update_fields=["name", "industry", "size", "updated_at"])
    record_event(
        "organization.updated",
        organization=org,
        actor=acting_user,
        message=f"Organization settings updated ({org.name}).",
        metadata={"organization_id": org.id},
    )
    return org


def create_invitation(
    org: Organization,
    email: str,
    role: str,
    invited_by=None,
) -> Invitation:
    if invited_by is not None:
        _ensure_admin(invited_by, org)

    email = (email or "").strip().lower()
    if not email:
        raise ValidationError("Email is required.")
    role = _validate_role(role or Membership.ROLE_VIEWER)

    active_existing = Invitation.objects.filter(
        organization=org,
        email=email,
        accepted_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists()
    if active_existing:
        raise ValidationError("An active invitation already exists for this email.")

    invite = Invitation.objects.create(
        organization=org,
        email=email,
        role=role,
        invited_by=invited_by,
        expires_at=Invitation.default_expiry(),
    )
    record_event(
        "invitation.created",
        organization=org,
        actor=invited_by,
        message=f"Invitation created for {email}.",
        metadata={"organization_id": org.id, "invite_id": invite.id},
    )
    return invite


def revoke_invitation(org: Organization, token, acting_user=None) -> Invitation:
    if acting_user is not None:
        _ensure_admin(acting_user, org)

    invite = Invitation.objects.filter(organization=org, token=token, accepted_at__isnull=True).first()
    if not invite:
        raise ValidationError("Invitation not found.")

    invite.expires_at = timezone.now()
    invite.save(update_fields=["expires_at"])
    record_event(
        "invitation.revoked",
        organization=org,
        actor=acting_user,
        message=f"Invitation revoked for {invite.email}.",
        metadata={"organization_id": org.id, "invite_id": invite.id},
    )
    return invite


def accept_invitation(token, password1: str, password2: str):
    invite = Invitation.objects.filter(token=token).first()
    if not invite:
        raise ValidationError("Invitation not found.")

    now = timezone.now()
    if invite.accepted_at is not None:
        raise ValidationError("This invitation has already been used.")
    if invite.expires_at and invite.expires_at <= now:
        raise ValidationError("This invitation has expired.")

    if password1 != password2 or len(password1 or "") < 8:
        raise ValidationError("Passwords must match and be at least 8 characters.")

    with transaction.atomic():
        user = User.objects.filter(email=invite.email).first()
        if not user:
            user = User.objects.create_user(email=invite.email, password=password1)
        else:
            user.set_password(password1)
            user.save(update_fields=["password"])

        Membership.objects.update_or_create(
            user=user,
            organization=invite.organization,
            defaults={"role": invite.role, "is_active": True},
        )
        invite.accepted_at = now
        invite.save(update_fields=["accepted_at"])

    record_event(
        "invitation.accepted",
        organization=invite.organization,
        actor=user,
        message=f"Invitation accepted by {user.email}.",
        metadata={"organization_id": invite.organization_id, "invite_id": invite.id},
    )
    return user, invite.organization, invite


def change_member_role(org: Organization, member_id: int, new_role: str, acting_user=None) -> Membership:
    if acting_user is not None:
        _ensure_admin(acting_user, org)

    role = _validate_role((new_role or "").strip())
    membership = Membership.objects.filter(id=member_id, organization=org).first()
    if not membership:
        raise ValidationError("Member not found.")

    if membership.role == Membership.ROLE_ADMIN and role != Membership.ROLE_ADMIN:
        admins_count = Membership.objects.filter(organization=org, role=Membership.ROLE_ADMIN, is_active=True).count()
        if admins_count <= 1:
            raise ValidationError("Cannot remove the last remaining admin.")

    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    record_event(
        "member.role_changed",
        organization=org,
        actor=acting_user,
        message=f"Member role changed to {role}.",
        metadata={"organization_id": org.id, "member_id": membership.id},
    )
    return membership


def deactivate_member(org: Organization, member_id: int, acting_user=None) -> Membership:
    if acting_user is not None:
        _ensure_admin(acting_user, org)

    membership = Membership.objects.filter(id=member_id, organization=org).first()
    if not membership:
        raise ValidationError("Member not found.")
    if acting_user is not None and membership.user_id == acting_user.id:
        raise ValidationError("You cannot deactivate yourself.")

    if membership.role == Membership.ROLE_ADMIN:
        admins_count = Membership.objects.filter(organization=org, role=Membership.ROLE_ADMIN, is_active=True).count()
        if admins_count <= 1:
            raise ValidationError("Cannot deactivate the last remaining admin.")

    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
    record_event(
        "member.deactivated",
        organization=org,
        actor=acting_user,
        message="Member deactivated.",
        metadata={"organization_id": org.id, "member_id": membership.id},
    )
    return membership
