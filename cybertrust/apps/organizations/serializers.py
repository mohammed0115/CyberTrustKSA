from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "industry", "size", "created_at"]
        read_only_fields = ["id", "created_at"]
