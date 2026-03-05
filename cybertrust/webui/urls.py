from django.urls import path

from . import views

app_name = "webui"

urlpatterns = [
    # Public
    path("", views.landing, name="landing"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # App home / pages (current org)
    path("app/", views.app_home, name="app_home"),
    path("app/controls/", views.app_controls, name="controls"),
    path("app/evidence/", views.app_evidence, name="evidence"),
    path("app/evidence/upload/", views.app_evidence_upload, name="app_evidence_upload"),
    path("app/analysis/<str:evidence_id>/", views.analysis_results, name="analysis_results"),
    path("app/reports/", views.reports, name="reports"),

    # Onboarding
    path("onboarding/org/", views.org_setup, name="org_setup"),
    path("onboarding/<slug:slug>/invite/", views.invite_team, name="invite_team"),

    # Org scoped
    path("org/<slug:slug>/dashboard/", views.dashboard, name="dashboard"),
    path("org/<slug:slug>/controls/", views.controls_list, name="controls_list"),
    path("org/<slug:slug>/controls/<int:control_id>/", views.control_detail, name="control_detail"),
    path("org/<slug:slug>/controls/<int:control_id>/analyze/", views.control_analyze, name="control_analyze"),
    path("org/<slug:slug>/evidence/", views.evidence_list, name="evidence_list"),
    path("org/<slug:slug>/evidence/upload/", views.evidence_upload, name="evidence_upload"),
    path("org/<slug:slug>/evidence/<int:evidence_id>/", views.evidence_detail, name="evidence_detail"),
    path(
        "org/<slug:slug>/evidence/<int:evidence_id>/analyze/<int:control_id>/",
        views.evidence_analyze,
        name="evidence_analyze",
    ),
    path("org/<slug:slug>/evidence/<int:evidence_id>/status/", views.evidence_status, name="evidence_status"),
    path("org/<slug:slug>/reports/", views.reports_list, name="reports_list"),
    path(
        "org/<slug:slug>/reports/<int:report_id>/download/",
        views.report_download,
        name="report_download",
    ),
    path("org/<slug:slug>/settings/", views.org_settings, name="org_settings"),
    path("org/<slug:slug>/members/", views.members_list, name="members_list"),
    path("org/<slug:slug>/members/<int:member_id>/role/", views.member_change_role, name="member_change_role"),
    path("org/<slug:slug>/members/<int:member_id>/deactivate/", views.member_deactivate, name="member_deactivate"),
    path("org/<slug:slug>/invites/", views.invites_list, name="invites_list"),
    path("org/<slug:slug>/invites/create/", views.invite_create, name="invite_create"),
    path("org/<slug:slug>/invites/<uuid:token>/revoke/", views.invite_revoke, name="invite_revoke"),

    # Public invite accept
    path("invites/accept/<uuid:token>/", views.invite_accept, name="invite_accept"),
]
