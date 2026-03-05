"""Controls App URLs - Cloud Integration Guides + Dashboard routing."""
from django.urls import path

from . import views

app_name = "controls"

urlpatterns = [
    # Cloud Integration Guides
    path("api/cloud-guides/", views.list_cloud_guides, name="list_guides"),
    path("api/cloud-guides/<str:provider>/<str:requirement>/", views.get_cloud_guide, name="get_guide"),
    path("api/cloud-guides/<str:provider>/checklist/", views.get_integration_checklist, name="checklist"),
    path("api/cloud-guides/<str:provider>/checklist/<slug:slug>/", views.get_integration_checklist, name="checklist_org"),
    
    # Compliance Dashboard & Controls
    path(
        "api/organizations/<str:org_slug>/dashboard/",
        views.get_dashboard,
        name="dashboard"
    ),
    path(
        "api/organizations/<str:org_slug>/controls/",
        views.list_controls,
        name="list_controls"
    ),
    path(
        "api/organizations/<str:org_slug>/controls/<int:control_id>/details/",
        views.get_control_details,
        name="control_details"
    ),
]
