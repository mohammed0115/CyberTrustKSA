import secrets

from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APITestCase

from cybertrust.apps.organizations.models import Organization

from .models import OrganizationInvite


class InviteFlowTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Acme Corp",
            slug="acme",
            industry="Tech",
            size="1-10",
        )
        User = get_user_model()
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="AdminPass123",
            organization=self.org,
            is_staff=True,
        )
        self.normal_user = User.objects.create_user(
            email="user@example.com",
            password="UserPass123",
            organization=self.org,
        )

    def test_invite_requires_org_admin(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(
            "/api/invites/",
            {"email": "invitee@example.com", "organization": self.org.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_invite_creation_sends_email(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/invites/",
            {"email": "invitee@example.com", "organization": self.org.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        invite = OrganizationInvite.objects.get(email="invitee@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invite.token, mail.outbox[0].body)

    def test_accept_invite_creates_user_and_sets_password(self):
        token = secrets.token_urlsafe(32)[:64]
        invite = OrganizationInvite.objects.create(
            email="joiner@example.com",
            organization=self.org,
            token=token,
            invited_by=self.admin_user,
        )
        response = self.client.post(
            "/api/invites/accept/",
            {"token": invite.token, "password": "JoinerPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        user = User.objects.get(email="joiner@example.com")
        self.assertTrue(user.check_password("JoinerPass123"))
        self.assertEqual(user.organization_id, self.org.id)
        invite.refresh_from_db()
        self.assertIsNotNone(invite.accepted_at)

        response_repeat = self.client.post(
            "/api/invites/accept/",
            {"token": invite.token, "password": "AnotherPass123"},
            format="json",
        )
        self.assertEqual(response_repeat.status_code, 400)
