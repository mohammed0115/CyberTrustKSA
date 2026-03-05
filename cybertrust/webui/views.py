from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from cybertrust.apps.ai_engine.models import AIAnalysisResult
from cybertrust.apps.ai_engine.services import list_results_for_evidence
from cybertrust.apps.audits.services import list_recent_events
from cybertrust.apps.controls.models import Control
from cybertrust.apps.controls.services import (
    get_category_scores,
    get_control,
    get_controls_overview,
    get_dashboard_kpis,
    list_controls,
)
from cybertrust.apps.evidence.services import (
    create_evidence,
    enqueue_analysis,
    get_evidence_for_org,
    link_evidence_to_controls,
    list_links_for_control,
    list_links_for_evidence,
    list_org_evidence,
)
from cybertrust.apps.organizations.domain import (
    PermissionDenied as OrgPermissionDenied,
    ValidationError as OrgValidationError,
    accept_invitation,
    change_member_role,
    create_invitation,
    create_organization,
    deactivate_member,
    get_current_org_for_user,
    get_invitation_by_token,
    get_membership,
    get_org_by_id,
    get_org_by_slug,
    is_admin,
    list_org_invites,
    list_org_members,
    list_user_memberships,
    revoke_invitation,
    split_invites,
    update_organization_settings,
)
from cybertrust.apps.organizations.models import Membership, Organization
from cybertrust.apps.reports.models import Report
from cybertrust.apps.reports.services import (
    generate_compliance_report,
    get_report_for_org,
    list_reports_for_org,
)
from .forms import InviteForm, LoginForm, OrgSettingsForm, RegisterForm

User = get_user_model()

LANG_SESSION_KEY = "lang"
DEFAULT_LANG = "ar"


def _set_lang(request: HttpRequest) -> None:
    lang = request.GET.get("lang")
    if lang in ("ar", "en"):
        request.session[LANG_SESSION_KEY] = lang


def _lang(request: HttpRequest) -> str:
    return request.session.get(LANG_SESSION_KEY, DEFAULT_LANG)


def _get_membership(user: User, org: Organization) -> Optional[Membership]:
    return get_membership(user, org)


def _get_current_org(request: HttpRequest) -> Optional[Organization]:
    if not request.user.is_authenticated:
        return None

    org_id = request.session.get("current_org_id")
    org = get_current_org_for_user(request.user, org_id)
    if org:
        request.session["current_org_id"] = str(org.id)
    return org


def _base_context(request: HttpRequest, **extra: Any) -> dict[str, Any]:
    _set_lang(request)
    is_ar = _lang(request) == "ar"
    org = extra.pop("org", None) or _get_current_org(request)
    membership = extra.pop("membership", None)
    if org and membership is None and request.user.is_authenticated:
        membership = _get_membership(request.user, org)

    ctx = {
        "is_ar": is_ar,
        "lang": "ar" if is_ar else "en",
        "dir": "rtl" if is_ar else "ltr",
        "app_name": "CyberTrustKSA",
        "now": timezone.now(),
        "org": org,
        "org_name": org.name if org else "—",
        "org_slug": org.slug if org else "",
        "org_role": membership.role if membership else "",
        "is_org_admin": is_admin(membership),
        "can_manage": bool(
            membership
            and membership.role in {Membership.ROLE_ADMIN, Membership.ROLE_SECURITY_OFFICER}
        ),
        "role_choices": Membership.ROLE_CHOICES,
    }
    ctx.update(extra)
    return ctx


def _add_form_errors(request: HttpRequest, form) -> None:
    for _, errors in form.errors.items():
        for error in errors:
            messages.error(request, error)


def _require_current_org(request: HttpRequest) -> Optional[tuple[Organization, Membership]]:
    org = _get_current_org(request)
    if not org:
        messages.error(request, "Select an organization to continue.")
        return None
    membership = _get_membership(request.user, org)
    if not membership:
        request.session.pop("current_org_id", None)
        messages.error(request, "Select an organization to continue.")
        return None
    return org, membership


def require_org_member(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(view_func)
    @login_required
    def _wrapped(request: HttpRequest, slug: str, *args, **kwargs) -> HttpResponse:
        org = get_org_by_slug(slug)
        if not org:
            raise Http404
        membership = _get_membership(request.user, org)
        if not membership:
            messages.error(request, "You do not have access to this organization.")
            return redirect("webui:app_home")
        request.current_org = org
        request.current_membership = membership
        request.session["current_org_id"] = str(org.id)
        return view_func(request, slug, *args, **kwargs)

    return _wrapped


def require_org_admin(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(view_func)
    @require_org_member
    def _wrapped(request: HttpRequest, slug: str, *args, **kwargs) -> HttpResponse:
        if not is_admin(request.current_membership):
            messages.error(request, "Admin access required.")
            return redirect("webui:dashboard", slug=request.current_org.slug)
        return view_func(request, slug, *args, **kwargs)

    return _wrapped


def require_org_roles(roles: set[str]):
    def decorator(view_func: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @wraps(view_func)
        @require_org_member
        def _wrapped(request: HttpRequest, slug: str, *args, **kwargs) -> HttpResponse:
            if request.current_membership.role not in roles:
                messages.error(request, "Permission denied.")
                return redirect("webui:dashboard", slug=request.current_org.slug)
            return view_func(request, slug, *args, **kwargs)

        return _wrapped

    return decorator


# =========================
# Public Pages
# =========================


def landing(request: HttpRequest) -> HttpResponse:
    return render(request, "webui/landing.html", _base_context(request))


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        org = _get_current_org(request)
        if org:
            return redirect("webui:dashboard", slug=org.slug)
        return redirect("webui:app_home")

    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            password = form.cleaned_data["password"]
            user = authenticate(request, username=email, password=password)
            if user:
                login(request, user)
                memberships = list_user_memberships(user)
                if not memberships.exists():
                    return redirect("webui:org_setup")
                if memberships.count() == 1:
                    org = memberships.first().organization
                    request.session["current_org_id"] = str(org.id)
                    return redirect("webui:dashboard", slug=org.slug)
                return redirect("webui:app_home")

            messages.error(request, "Invalid email or password.")
        else:
            _add_form_errors(request, form)

    return render(request, "webui/auth/login.html", _base_context(request))


@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        org = _get_current_org(request)
        if org:
            return redirect("webui:dashboard", slug=org.slug)
        return redirect("webui:app_home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = User.objects.create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
            )
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("webui:org_setup")
        _add_form_errors(request, form)

    return render(request, "webui/auth/register.html", _base_context(request))


@require_http_methods(["GET", "POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("webui:landing")


# =========================
# App Home + Onboarding
# =========================


@require_http_methods(["GET", "POST"])
@login_required
def app_home(request: HttpRequest) -> HttpResponse:
    memberships = list_user_memberships(request.user)
    if request.method == "POST":
        org_id = request.POST.get("org_id")
        if org_id:
            org = get_org_by_id(org_id)
            if org and _get_membership(request.user, org):
                request.session["current_org_id"] = str(org.id)
                return redirect("webui:dashboard", slug=org.slug)
        messages.error(request, "Invalid organization selection.")

    return render(request, "webui/app/home.html", _base_context(request, memberships=memberships))


@require_http_methods(["GET", "POST"])
@login_required
def org_setup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        name = (request.POST.get("org_name") or "").strip()
        industry = (request.POST.get("industry") or "").strip()
        size = (request.POST.get("size") or "").strip()
        try:
            org = create_organization(request.user, name=name, industry=industry, size=size)
        except OrgValidationError as exc:
            messages.error(request, str(exc))
            return render(request, "webui/onboarding/org_setup.html", _base_context(request))
        except OrgPermissionDenied as exc:
            messages.error(request, str(exc))
            return redirect("webui:login")

        request.session["current_org_id"] = str(org.id)
        messages.success(request, "Organization created.")
        return redirect("webui:invite_team", slug=org.slug)

    return render(request, "webui/onboarding/org_setup.html", _base_context(request))


@require_http_methods(["GET", "POST"])
@require_org_admin
def invite_team(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    invite_link = None

    if request.method == "POST":
        form = InviteForm(request.POST or None)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            role = form.cleaned_data.get("role") or Membership.ROLE_VIEWER
            try:
                invite = create_invitation(org, email=email, role=role, invited_by=request.user)
            except OrgValidationError as exc:
                messages.error(request, str(exc))
            except OrgPermissionDenied as exc:
                messages.error(request, str(exc))
            else:
                invite_link = request.build_absolute_uri(
                    reverse("webui:invite_accept", kwargs={"token": invite.token})
                )
                messages.success(request, "Invitation created.")
        else:
            _add_form_errors(request, form)

    return render(request, "webui/onboarding/invite_team.html", _base_context(request, org=org, invite_link=invite_link))


# =========================
# Dashboard (Org Scoped)
# =========================


@require_org_member
def dashboard(request: HttpRequest, slug: str) -> HttpResponse:
    ctx = _base_context(request, org=request.current_org, membership=request.current_membership)
    kpi_data = get_dashboard_kpis(request.current_org)
    total_controls = Control.objects.filter(is_active=True).count()

    compliance_data = []
    for row in get_category_scores(request.current_org):
        category = row["category"]
        compliance_data.append(
            {
                "category_ar": category.name_ar,
                "category_en": category.name_en,
                "score": row["score"],
            }
        )

    kpis = [
        {
            "label_ar": "???? ????????",
            "label_en": "Compliance Score",
            "value": f"{kpi_data['overall_score']}%",
            "icon": "shield",
        },
        {
            "label_ar": "??????? ????????",
            "label_en": "Controls Completed",
            "value": f"{kpi_data['controls_completed']}/{total_controls}",
            "icon": "file",
        },
        {
            "label_ar": "???? ??? ????????",
            "label_en": "Evidence Pending",
            "value": str(kpi_data["evidence_pending"]),
            "icon": "alert",
        },
        {
            "label_ar": "????? ???????",
            "label_en": "Risk Level",
            "value": "?????" if kpi_data["risk_level"] == "LOW" else "?????" if kpi_data["risk_level"] == "MEDIUM" else "?????",
            "icon": "trend",
        },
    ]

    recent_activity = []
    for event in list_recent_events(request.current_org, limit=5):
        recent_activity.append(
            {
                "text_ar": event.message or event.event_type,
                "text_en": event.message or event.event_type,
                "time": event.created_at.strftime("%H:%M"),
            }
        )

    return render(
        request,
        "webui/app/dashboard.html",
        {
            **ctx,
            "kpis": kpis,
            "compliance_data": compliance_data,
            "recent_activity": recent_activity,
            "missing_controls": kpi_data["missing_controls"],
        },
    )

# =========================
# App Pages (Current Org)
# =========================


@login_required
def app_controls(request: HttpRequest) -> HttpResponse:
    current = _require_current_org(request)
    if not current:
        return redirect("webui:app_home")
    org, _ = current
    return redirect("webui:controls_list", slug=org.slug)


@login_required
def app_evidence(request: HttpRequest) -> HttpResponse:
    current = _require_current_org(request)
    if not current:
        return redirect("webui:app_home")
    org, _ = current
    return redirect("webui:evidence_list", slug=org.slug)


@login_required
def app_evidence_upload(request: HttpRequest) -> HttpResponse:
    current = _require_current_org(request)
    if not current:
        return redirect("webui:app_home")
    org, _ = current
    return redirect("webui:evidence_upload", slug=org.slug)


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    current = _require_current_org(request)
    if not current:
        return redirect("webui:app_home")
    org, _ = current
    return redirect("webui:reports_list", slug=org.slug)


# =========================
# Controls + Evidence (Org Scoped)
# =========================


@require_http_methods(["GET", "POST"])
@require_org_member
def reports_list(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org

    if request.method == "POST":
        if request.current_membership.role not in {
            Membership.ROLE_ADMIN,
            Membership.ROLE_SECURITY_OFFICER,
        }:
            messages.error(request, "Permission denied.")
            return redirect("webui:reports_list", slug=org.slug)
        try:
            generate_compliance_report(org, created_by=request.user)
        except Exception as exc:
            messages.error(request, f"Report generation failed: {exc}")
        else:
            messages.success(request, "Report generated successfully.")
        return redirect("webui:reports_list", slug=org.slug)

    reports = list_reports_for_org(org)
    return render(
        request,
        "webui/app/reports.html",
        _base_context(request, org=org, reports=reports),
    )


@require_org_member
def report_download(request: HttpRequest, slug: str, report_id: int) -> HttpResponse:
    org = request.current_org
    report = get_report_for_org(org, report_id)
    if not report:
        raise Http404
    if report.status != Report.STATUS_READY or not report.file:
        messages.error(request, "Report is not ready yet.")
        return redirect("webui:reports_list", slug=org.slug)

    filename = report.file.name.rsplit("/", 1)[-1]
    return FileResponse(report.file.open("rb"), as_attachment=True, filename=filename)


@require_org_member
def controls_list(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    controls = get_controls_overview(org)
    return render(request, "webui/app/controls.html", _base_context(request, org=org, controls=controls))


@require_org_member
def control_detail(request: HttpRequest, slug: str, control_id: int) -> HttpResponse:
    org = request.current_org
    control = get_control(control_id)
    if not control:
        raise Http404
    links = list_links_for_control(org, control)
    results = (
        AIAnalysisResult.objects.filter(organization=org, control=control)
        .select_related("evidence")
        .order_by("-created_at")
    )
    return render(
        request,
        "webui/app/control_detail.html",
        _base_context(request, org=org, control=control, links=links, results=results),
    )


@require_http_methods(["POST"])
@require_org_roles({Membership.ROLE_ADMIN, Membership.ROLE_SECURITY_OFFICER})
def control_analyze(request: HttpRequest, slug: str, control_id: int) -> HttpResponse:
    org = request.current_org
    control = get_control(control_id)
    if not control:
        raise Http404
    evidence_id = request.POST.get("evidence_id")
    evidence = get_evidence_for_org(org, evidence_id)
    if not evidence:
        messages.error(request, "Evidence not found.")
        return redirect("webui:control_detail", slug=org.slug, control_id=control.id)

    try:
        link_evidence_to_controls(evidence, [control.id], linked_by=request.user)
    except Exception:
        pass

    enqueue_analysis(evidence.id, [control.id])
    messages.success(request, "Analysis started.")
    return redirect("webui:control_detail", slug=org.slug, control_id=control.id)


@require_org_member
def evidence_list(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    evidence_items = list_org_evidence(org).prefetch_related("control_links", "control_links__control")
    return render(
        request,
        "webui/app/evidence.html",
        _base_context(request, org=org, evidence_items=evidence_items),
    )


@require_http_methods(["GET", "POST"])
@require_org_roles({Membership.ROLE_ADMIN, Membership.ROLE_SECURITY_OFFICER})
def evidence_upload(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    controls = list_controls()
    selected_control = request.GET.get("control")

    if request.method == "POST":
        file_obj = request.FILES.get("file")
        control_id = request.POST.get("control_id") or selected_control
        control_ids = [control_id] if control_id else []
        try:
            evidence = create_evidence(
                organization=org,
                uploaded_by=request.user,
                file_obj=file_obj,
                control_ids=control_ids,
            )
        except Exception as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Evidence uploaded successfully.")
            return redirect("webui:evidence_detail", slug=org.slug, evidence_id=evidence.id)

    steps = [
        {"name_ar": "??? ?????", "name_en": "Upload", "status": "completed"},
        {"name_ar": "??????? ????", "name_en": "Extract", "status": "active"},
        {"name_ar": "?????? ???????", "name_en": "Match", "status": "queued"},
        {"name_ar": "????? AI", "name_en": "Analyze", "status": "queued"},
        {"name_ar": "???????", "name_en": "Report", "status": "queued"},
    ]

    return render(
        request,
        "webui/app/evidence_upload.html",
        _base_context(
            request,
            org=org,
            controls=controls,
            selected_control=selected_control,
            steps=steps,
        ),
    )


@require_org_member
def evidence_detail(request: HttpRequest, slug: str, evidence_id: int) -> HttpResponse:
    org = request.current_org
    evidence = get_evidence_for_org(org, evidence_id)
    if not evidence:
        raise Http404
    links = list_links_for_evidence(evidence)
    results = list_results_for_evidence(evidence)
    total_controls = links.count()
    analyzed_controls = results.values("control").distinct().count()
    excerpt = (evidence.extracted_text or "")[:600]

    return render(
        request,
        "webui/app/evidence_detail.html",
        _base_context(
            request,
            org=org,
            evidence=evidence,
            links=links,
            results=results,
            total_controls=total_controls,
            analyzed_controls=analyzed_controls,
            extracted_excerpt=excerpt,
        ),
    )


@require_http_methods(["POST"])
@require_org_roles({Membership.ROLE_ADMIN, Membership.ROLE_SECURITY_OFFICER})
def evidence_analyze(request: HttpRequest, slug: str, evidence_id: int, control_id: int) -> HttpResponse:
    org = request.current_org
    evidence = get_evidence_for_org(org, evidence_id)
    control = get_control(control_id)
    if not evidence or not control:
        raise Http404

    try:
        link_evidence_to_controls(evidence, [control.id], linked_by=request.user)
    except Exception:
        pass

    enqueue_analysis(evidence.id, [control.id])
    messages.success(request, "Analysis started.")
    return redirect("webui:evidence_detail", slug=org.slug, evidence_id=evidence.id)


@require_org_member
def evidence_status(request: HttpRequest, slug: str, evidence_id: int) -> HttpResponse:
    org = request.current_org
    evidence = get_evidence_for_org(org, evidence_id)
    if not evidence:
        raise Http404
    links = list_links_for_evidence(evidence).count()
    analyzed = list_results_for_evidence(evidence).values("control").distinct().count()
    status = evidence.status

    status_progress = {
        "UPLOADED": (15, "Uploaded"),
        "EXTRACTING": (35, "Extracting text"),
        "PROCESSING": (35, "Extracting text"),
        "EXTRACTED": (55, "Text extracted"),
        "ANALYZING": (75, "AI analyzing"),
        "ANALYZED": (100, "Analysis complete"),
        "FAILED": (0, evidence.error_message or "Analysis failed"),
    }
    progress, message = status_progress.get(status, (0, "Pending"))
    return JsonResponse(
        {
            "status": status,
            "linked_controls": links,
            "analyzed_controls": analyzed,
            "progress": progress,
            "message": message,
        }
    )


@login_required
def analysis_results(request: HttpRequest, evidence_id: str) -> HttpResponse:
    current = _require_current_org(request)
    if not current:
        return redirect("webui:app_home")
    org, _ = current
    return redirect("webui:evidence_detail", slug=org.slug, evidence_id=evidence_id)

# =========================
# Org Settings / Members / Invites (ADMIN)
# =========================


@require_http_methods(["GET", "POST"])
@require_org_admin
def org_settings(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org

    if request.method == "POST":
        form = OrgSettingsForm(
            {
                "name": (request.POST.get("name") or "").strip(),
                "industry": (request.POST.get("industry") or "").strip(),
                "size": (request.POST.get("size") or "").strip(),
            }
        )
        if form.is_valid():
            try:
                update_organization_settings(
                    org,
                    name=form.cleaned_data["name"],
                    industry=form.cleaned_data.get("industry", ""),
                    size=form.cleaned_data.get("size", ""),
                    acting_user=request.user,
                )
            except OrgValidationError as exc:
                messages.error(request, str(exc))
            except OrgPermissionDenied as exc:
                messages.error(request, str(exc))
                return redirect("webui:dashboard", slug=org.slug)
            else:
                messages.success(request, "Settings updated.")
                return redirect("webui:org_settings", slug=org.slug)
        else:
            _add_form_errors(request, form)

    return render(request, "webui/org/settings.html", _base_context(request, org=org))


@require_org_admin
def members_list(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    members = list_org_members(org)
    return render(request, "webui/org/members.html", _base_context(request, org=org, members=members))


@require_http_methods(["POST"])
@require_org_admin
def member_change_role(request: HttpRequest, slug: str, member_id: int) -> HttpResponse:
    org = request.current_org
    new_role = (request.POST.get("role") or "").strip()
    try:
        change_member_role(org, member_id=member_id, new_role=new_role, acting_user=request.user)
    except OrgValidationError as exc:
        messages.error(request, str(exc))
    except OrgPermissionDenied as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Member role updated.")
    return redirect("webui:members_list", slug=org.slug)


@require_http_methods(["POST"])
@require_org_admin
def member_deactivate(request: HttpRequest, slug: str, member_id: int) -> HttpResponse:
    org = request.current_org
    try:
        deactivate_member(org, member_id=member_id, acting_user=request.user)
    except OrgValidationError as exc:
        messages.error(request, str(exc))
    except OrgPermissionDenied as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Member deactivated.")
    return redirect("webui:members_list", slug=org.slug)


@require_org_admin
def invites_list(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    invites = list_org_invites(org)
    active, expired, accepted = split_invites(invites)

    return render(
        request,
        "webui/org/invites.html",
        _base_context(request, org=org, active=active, expired=expired, accepted=accepted),
    )


@require_http_methods(["POST"])
@require_org_admin
def invite_create(request: HttpRequest, slug: str) -> HttpResponse:
    org = request.current_org
    form = InviteForm(request.POST or None)
    if not form.is_valid():
        _add_form_errors(request, form)
        return redirect("webui:invites_list", slug=org.slug)

    email = form.cleaned_data["email"].strip().lower()
    role = form.cleaned_data.get("role") or Membership.ROLE_VIEWER
    try:
        create_invitation(org, email=email, role=role, invited_by=request.user)
    except OrgValidationError as exc:
        messages.error(request, str(exc))
    except OrgPermissionDenied as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Invitation created.")
    return redirect("webui:invites_list", slug=org.slug)


@require_http_methods(["POST"])
@require_org_admin
def invite_revoke(request: HttpRequest, slug: str, token) -> HttpResponse:
    org = request.current_org
    try:
        revoke_invitation(org, token=token, acting_user=request.user)
    except OrgValidationError as exc:
        messages.error(request, str(exc))
    except OrgPermissionDenied as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Invitation revoked.")
    return redirect("webui:invites_list", slug=org.slug)


@require_http_methods(["GET", "POST"])
def invite_accept(request: HttpRequest, token) -> HttpResponse:
    invite = get_invitation_by_token(token)
    if not invite:
        raise Http404
    now = timezone.now()

    if invite.accepted_at is not None:
        messages.info(request, "This invitation has already been used.")
        return redirect("webui:login")
    if invite.expires_at and invite.expires_at <= now:
        messages.error(request, "This invitation has expired.")
        return redirect("webui:login")

    if request.method == "POST":
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""
        try:
            user, org, _ = accept_invitation(token=token, password1=password1, password2=password2)
        except OrgValidationError as exc:
            messages.error(request, str(exc))
            return render(request, "webui/auth/accept_invite.html", _base_context(request, invite=invite))
        else:
            login(request, user)
            request.session["current_org_id"] = str(org.id)
            messages.success(request, "Invitation accepted.")
            return redirect("webui:dashboard", slug=org.slug)

    return render(request, "webui/auth/accept_invite.html", _base_context(request, invite=invite))
