import secrets

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import serializers

from .models import OrganizationInvite

User = get_user_model()


class OrganizationInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationInvite
        fields = [
            "id",
            "email",
            "organization",
            "token",
            "invited_by",
            "created_at",
            "accepted_at",
        ]
        read_only_fields = ["id", "token", "invited_by", "created_at", "accepted_at"]
        extra_kwargs = {"organization": {"required": False}}

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs
        user = request.user
        organization = attrs.get("organization")
        if user.is_superuser or user.is_staff:
            if organization is None:
                raise serializers.ValidationError({"organization": "Organization is required."})
            return attrs
        if not user.organization_id:
            raise serializers.ValidationError({"organization": "You are not assigned to an organization."})
        if organization and user.organization_id != organization.id:
            raise serializers.ValidationError({"organization": "You can only invite users to your organization."})
        attrs["organization"] = user.organization
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user and user.is_authenticated:
            validated_data["invited_by"] = user

        token = secrets.token_urlsafe(32)[:64]
        while OrganizationInvite.objects.filter(token=token).exists():
            token = secrets.token_urlsafe(32)[:64]
        validated_data["token"] = token

        invite = super().create(validated_data)

        send_mail(
            subject="You're invited to CyberTrust",
            message=(
                "You have been invited to join an organization.\n"
                f"Invite token: {invite.token}\n"
                "Use this token to accept the invitation."
            ),
            from_email=None,
            recipient_list=[invite.email],
            fail_silently=False,
        )

        return invite


class OrganizationInviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        token = attrs.get("token")
        invite = OrganizationInvite.objects.filter(token=token, accepted_at__isnull=True).first()
        if not invite:
            raise serializers.ValidationError("Invalid or already accepted invitation.")
        if User.objects.filter(email=invite.email).exists():
            raise serializers.ValidationError("User with this email already exists.")
        attrs["invite"] = invite
        return attrs

    def create(self, validated_data):
        invite = validated_data["invite"]
        user = User.objects.create_user(
            email=invite.email,
            password=validated_data["password"],
            organization=invite.organization,
            is_active=True,
        )
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["accepted_at"])
        return user
