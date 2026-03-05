from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OrganizationInviteViewSet, me

router = DefaultRouter()
router.register(r"invites", OrganizationInviteViewSet, basename="invites")

urlpatterns = [
    path("me/", me, name="me"),
    path("", include(router.urls)),
]
