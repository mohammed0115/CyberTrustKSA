
from django.urls import path
from . import views

urlpatterns = [
    path("app/", views.app_home, name="app_home"),
    path("orgs/create/", views.create_org, name="create_org"),
    path("org/<slug:slug>/members/", views.members, name="members"),
    path("org/<slug:slug>/invite/", views.invite_member, name="invite_member"),
]
