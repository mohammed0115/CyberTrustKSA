
from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from .models import Membership, Organization


def _get_membership(request: HttpRequest, org: Organization):
    if not request.user.is_authenticated:
        return None
    return Membership.objects.filter(user=request.user, organization=org, is_active=True).first()


def require_org_member(view_func: Callable):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        org = kwargs.get("org")
        if org is None:
            return view_func(request, *args, **kwargs)
        m = _get_membership(request, org)
        if not m:
            messages.error(request, "ليس لديك صلاحية للوصول لهذه المنظمة." if request.session.get("lang","ar")=="ar" else "You don't have access to this organization.")
            return redirect("webui:app_home")
        request.org_membership = m
        return view_func(request, *args, **kwargs)
    return _wrapped


def require_org_roles(roles: Iterable[str]):
    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            org = kwargs.get("org")
            if org is None:
                return view_func(request, *args, **kwargs)
            m = _get_membership(request, org)
            if not m or m.role not in set(roles):
                messages.error(request, "ليس لديك صلاحية." if request.session.get("lang","ar")=="ar" else "Forbidden.")
                return redirect("webui:app_home")
            request.org_membership = m
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def require_org_admin(view_func: Callable):
    return require_org_roles([Membership.ROLE_ADMIN])(view_func)
