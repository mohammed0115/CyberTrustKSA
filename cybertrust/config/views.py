
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from cybertrust.apps.organizations.models import Organization, Membership, Invitation


User = get_user_model()


def _set_lang(request: HttpRequest) -> None:
    lang = request.GET.get("lang")
    if lang in ("ar", "en"):
        request.session["lang"] = lang


def _lang(request: HttpRequest) -> str:
    return request.session.get("lang", "ar")  # default Arabic


def _ensure_unique_slug(base: str) -> str:
    s = slugify(base)[:50].strip("-")
    if not s:
        s = f"org-{uuid.uuid4().hex[:8]}"
    candidate = s
    i = 1
    while Organization.objects.filter(slug=candidate).exists():
        i += 1
        candidate = f"{s}-{i}"
    return candidate


def _get_current_org(request: HttpRequest) -> Optional[Organization]:
    if not request.user.is_authenticated:
        return None
    org_id = request.session.get("current_org_id")
    if org_id:
        try:
            org = Organization.objects.filter(id=org_id, is_active=True).first()
            if org and Membership.objects.filter(user=request.user, organization=org, is_active=True).exists():
                return org
        except Exception:
            pass

    m = Membership.objects.select_related("organization").filter(user=request.user, is_active=True, organization__is_active=True).first()
    if m:
        request.session["current_org_id"] = str(m.organization_id)
        return m.organization
    return None


def _get_membership(request: HttpRequest, org: Organization) -> Optional[Membership]:
    if not request.user.is_authenticated or not org:
        return None
    return Membership.objects.filter(user=request.user, organization=org, is_active=True).first()


def _ctx(request: HttpRequest, **extra: Any) -> dict[str, Any]:
    is_ar = _lang(request) == "ar"
    org = _get_current_org(request)
    membership = _get_membership(request, org) if org else None
    base = {
        "is_ar": is_ar,
        "lang": "ar" if is_ar else "en",
        "dir": "rtl" if is_ar else "ltr",
        "app_name": "CyberTrust",
        "now": datetime.now(),
        "org": org,
        "org_name": org.name if org else ("—" if is_ar else "—"),
        "org_slug": org.slug if org else "",
        "org_role": membership.role if membership else "",
        "is_org_admin": bool(membership and membership.role == Membership.ROLE_ADMIN),
    }
    base.update(extra)
    return base


def landing(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    return render(request, "webui/landing.html", _ctx(request))


def login_view(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            # if user has org -> go dashboard else onboarding
            if Membership.objects.filter(user=user, is_active=True).exists():
                return redirect(reverse("webui:dashboard"))
            return redirect(reverse("webui:org_setup"))
        messages.error(request, "بيانات الدخول غير صحيحة." if _lang(request) == "ar" else "Invalid credentials.")
    return render(request, "webui/auth/login.html", _ctx(request))


def register_view(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""

        if not email or "@" not in email:
            messages.error(request, "البريد الإلكتروني غير صالح." if _lang(request) == "ar" else "Invalid email.")
            return render(request, "webui/auth/register.html", _ctx(request))

        if password1 != password2 or len(password1) < 8:
            messages.error(
                request,
                "كلمة المرور يجب أن تكون 8 أحرف على الأقل وتتطابق." if _lang(request) == "ar" else "Passwords must match and be 8+ chars."
            )
            return render(request, "webui/auth/register.html", _ctx(request))

        if User.objects.filter(email=email).exists():
            messages.error(request, "الحساب موجود بالفعل." if _lang(request) == "ar" else "Account already exists.")
            return render(request, "webui/auth/register.html", _ctx(request))

        user = User.objects.create_user(email=email, password=password1, first_name=first_name, last_name=last_name)
        login(request, user)
        return redirect(reverse("webui:org_setup"))

    return render(request, "webui/auth/register.html", _ctx(request))


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect(reverse("webui:landing"))


@login_required
def app_home(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    memberships = Membership.objects.select_related("organization").filter(user=request.user, is_active=True, organization__is_active=True).order_by("organization__name")
    if request.method == "POST":
        org_id = request.POST.get("org_id")
        if org_id:
            org = Organization.objects.filter(id=org_id, is_active=True).first()
            if org and Membership.objects.filter(user=request.user, organization=org, is_active=True).exists():
                request.session["current_org_id"] = str(org.id)
                return redirect(reverse("webui:dashboard"))
        messages.error(request, "اختيار منظمة غير صالح." if _lang(request) == "ar" else "Invalid organization.")
    return render(request, "webui/app/home.html", _ctx(request, memberships=memberships))


@login_required
def org_setup(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if request.method == "POST":
        org_name = (request.POST.get("org_name") or "").strip()
        industry = (request.POST.get("industry") or "").strip()
        size = (request.POST.get("size") or "").strip()
        if not org_name:
            messages.error(request, "اسم المنظمة مطلوب." if _lang(request) == "ar" else "Organization name is required.")
            return render(request, "webui/onboarding/org_setup.html", _ctx(request))

        slug = _ensure_unique_slug(org_name)
        org = Organization.objects.create(name=org_name, slug=slug, industry=industry, size=size, is_active=True)
        Membership.objects.create(user=request.user, organization=org, role=Membership.ROLE_ADMIN, is_active=True)
        request.session["current_org_id"] = str(org.id)

        messages.success(request, "تم إنشاء المنظمة بنجاح." if _lang(request) == "ar" else "Organization created.")
        return redirect(reverse("webui:invite_team"))

    return render(request, "webui/onboarding/org_setup.html", _ctx(request))


@login_required
def invite_team(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    org = _get_current_org(request)
    if not org:
        return redirect(reverse("webui:org_setup"))

    membership = _get_membership(request, org)
    if not membership or membership.role != Membership.ROLE_ADMIN:
        messages.error(request, "هذه الصفحة للمسؤول فقط." if _lang(request) == "ar" else "Admins only.")
        return redirect(reverse("webui:dashboard"))

    invite_link = None

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        role = (request.POST.get("role") or Membership.ROLE_VIEWER).strip()
        if not email or "@" not in email:
            messages.error(request, "البريد الإلكتروني غير صالح." if _lang(request) == "ar" else "Invalid email.")
            return render(request, "webui/onboarding/invite_team.html", _ctx(request, invite_link=None))

        active_existing = Invitation.objects.filter(organization=org, email=email, accepted_at__isnull=True, expires_at__gt=timezone.now()).exists()
        if active_existing:
            messages.error(request, "توجد دعوة نشطة لهذا البريد." if _lang(request) == "ar" else "Active invite already exists.")
            return render(request, "webui/onboarding/invite_team.html", _ctx(request, invite_link=None))

        inv = Invitation.objects.create(
            organization=org,
            email=email,
            role=role if role in dict(Membership.ROLE_CHOICES) else Membership.ROLE_VIEWER,
            invited_by=request.user,
            expires_at=Invitation.default_expiry(),
        )

        invite_link = request.build_absolute_uri(reverse("webui:accept_invite", kwargs={"token": str(inv.token)}))
        messages.success(request, "تم إنشاء الدعوة." if _lang(request) == "ar" else "Invitation created.")

        # Continue to dashboard after creating at least one invite
        return render(request, "webui/onboarding/invite_team.html", _ctx(request, invite_link=invite_link))

    return render(request, "webui/onboarding/invite_team.html", _ctx(request, invite_link=invite_link))


def accept_invite(request: HttpRequest, token: str) -> HttpResponse:
    _set_lang(request)
    inv = Invitation.objects.select_related("organization").filter(token=token).first()
    if not inv:
        messages.error(request, "الرابط غير صحيح." if _lang(request) == "ar" else "Invalid invite link.")
        return redirect(reverse("webui:login"))
    if inv.is_expired:
        messages.error(request, "انتهت صلاحية الدعوة." if _lang(request) == "ar" else "Invite expired.")
        return redirect(reverse("webui:login"))
    if inv.is_accepted:
        messages.info(request, "تم استخدام الدعوة مسبقاً." if _lang(request) == "ar" else "Invite already used.")
        return redirect(reverse("webui:login"))

    if request.method == "POST":
        password1 = request.POST.get("password1") or ""
        password2 = request.POST.get("password2") or ""
        if password1 != password2 or len(password1) < 8:
            messages.error(request, "كلمة المرور يجب أن تكون 8 أحرف على الأقل وتتطابق." if _lang(request) == "ar" else "Passwords must match and be 8+ chars.")
            return render(request, "webui/auth/accept_invite.html", _ctx(request, invite=inv))

        user = User.objects.filter(email=inv.email).first()
        if not user:
            user = User.objects.create_user(email=inv.email, password=password1, first_name="", last_name="")
        else:
            user.set_password(password1)
            user.save(update_fields=["password"])

        Membership.objects.update_or_create(
            user=user,
            organization=inv.organization,
            defaults={"role": inv.role, "is_active": True},
        )
        inv.accepted_at = timezone.now()
        inv.save(update_fields=["accepted_at"])

        login(request, user)
        request.session["current_org_id"] = str(inv.organization_id)
        return redirect(reverse("webui:dashboard"))

    return render(request, "webui/auth/accept_invite.html", _ctx(request, invite=inv))


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if not _get_current_org(request):
        return redirect(reverse("webui:app_home"))

    compliance_data = [
        {"category": "التحكم بالوصول" if _lang(request)=="ar" else "Access Control", "score": 92},
        {"category": "أمن الشبكة" if _lang(request)=="ar" else "Network Security", "score": 85},
        {"category": "حماية البيانات" if _lang(request)=="ar" else "Data Protection", "score": 78},
        {"category": "الاستجابة للحوادث" if _lang(request)=="ar" else "Incident Response", "score": 88},
    ]
    return render(request, "webui/app/dashboard.html", _ctx(request,
        kpis=[
            {"label_ar":"درجة الامتثال","label_en":"Compliance Score","value":"78%","icon":"shield"},
            {"label_ar":"الضوابط المكتملة","label_en":"Controls Completed","value":"64/114","icon":"file"},
            {"label_ar":"أدلة قيد المراجعة","label_en":"Evidence Pending","value":"12","icon":"alert"},
            {"label_ar":"مستوى المخاطر","label_en":"Risk Level","value":"Medium","icon":"trend"},
        ],
        compliance_data=compliance_data,
        recent_activity=[
            {"text_ar":"تم تحليل ملف policy_access.pdf","text_en":"Analyzed policy_access.pdf","time":"5m"},
            {"text_ar":"تم إنشاء دعوة لعضو جديد","text_en":"Created a new invitation","time":"22m"},
            {"text_ar":"تم رفع دليل جديد","text_en":"Uploaded new evidence","time":"1h"},
        ],
    ))


@login_required
def controls(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if not _get_current_org(request):
        return redirect(reverse("webui:app_home"))
    # Demo table (Sprint 2 will connect to real controls)
    controls_data = [
        {"code": "ECC-1-1", "title_ar": "سياسة التحكم بالوصول", "title_en": "Access Control Policy", "risk": "High", "evidence": 2, "score": 78},
        {"code": "ECC-2-3", "title_ar": "إدارة الثغرات", "title_en": "Vulnerability Management", "risk": "Medium", "evidence": 1, "score": 65},
        {"code": "ECC-3-2", "title_ar": "حماية البيانات", "title_en": "Data Protection", "risk": "High", "evidence": 0, "score": 0},
    ]
    return render(request, "webui/app/controls.html", _ctx(request, controls=controls_data))


@login_required
def evidence(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if not _get_current_org(request):
        return redirect(reverse("webui:app_home"))
    evidence_items = [
        {"id": "EV-001", "name": "security_policy.pdf", "status": "Analyzed", "score": 72, "time": "Today"},
        {"id": "EV-002", "name": "network_diagram.png", "status": "Analyzing", "score": None, "time": "5m ago"},
        {"id": "EV-003", "name": "incident_response.docx", "status": "Needs Work", "score": 54, "time": "Yesterday"},
    ]
    return render(request, "webui/app/evidence.html", _ctx(request, evidence_items=evidence_items))


@login_required
def evidence_upload(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if not _get_current_org(request):
        return redirect(reverse("webui:app_home"))
    if request.method == "POST":
        messages.success(request, "تم رفع الملف وبدأ التحليل (تجريبيًا)." if _lang(request) == "ar" else "File uploaded and analysis started (demo).")
        return redirect(reverse("webui:evidence"))
    return render(request, "webui/app/evidence_upload.html", _ctx(request))


@login_required
def analysis_results(request: HttpRequest, evidence_id: str) -> HttpResponse:
    _set_lang(request)
    if not _get_current_org(request):
        return redirect(reverse("webui:app_home"))
    analysis = {
        "control": "ECC-1-1",
        "title_ar": "سياسة التحكم بالوصول",
        "title_en": "Access Control Policy",
        "presence": "Partial",
        "score": 72,
        "missing": [
            "Password complexity rule",
            "Quarterly access review process",
            "Privileged accounts approval workflow",
        ],
        "recs": [
            "Define password policy with complexity + rotation rules.",
            "Schedule quarterly access reviews and store evidence.",
            "Implement privileged access request/approval workflow.",
        ],
        "confidence": 0.87,
    }
    return render(request, "webui/app/analysis_results.html", _ctx(request, analysis=analysis))


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    _set_lang(request)
    if not _get_current_org(request):
        return redirect(reverse("webui:app_home"))
    return render(request, "webui/app/reports.html", _ctx(request))
