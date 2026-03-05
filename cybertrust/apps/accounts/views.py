from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import OrganizationInvite
from .permissions import IsOrgAdmin
from .serializers import OrganizationInviteAcceptSerializer, OrganizationInviteSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response(
        {
            "id": user.id,
            "email": user.email,
            "organization_id": user.organization_id,
        }
    )


class OrganizationInviteViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationInviteSerializer
    permission_classes = [IsOrgAdmin]
    queryset = OrganizationInvite.objects.select_related("organization", "invited_by")

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return qs
        if user.organization_id:
            return qs.filter(organization_id=user.organization_id)
        return qs.none()

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], url_path="accept")
    def accept(self, request):
        serializer = OrganizationInviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"id": user.id, "email": user.email, "organization_id": user.organization_id},
            status=status.HTTP_200_OK,
        )
