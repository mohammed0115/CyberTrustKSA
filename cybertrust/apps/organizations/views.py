
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Organization, Membership, Invitation
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def app_home(request):
    orgs = Organization.objects.filter(membership__user=request.user)
    return render(request,"webui/app_home.html",{"orgs":orgs})

@login_required
def create_org(request):
    if request.method == "POST":
        name = request.POST.get("name")
        slug = request.POST.get("slug")
        industry = request.POST.get("industry")
        size = request.POST.get("size")

        org = Organization.objects.create(
            name=name,
            slug=slug,
            industry=industry,
            size=size
        )

        Membership.objects.create(
            user=request.user,
            organization=org,
            role="ADMIN"
        )

        messages.success(request,"Organization created successfully")
        return redirect("/app/")

    return render(request,"webui/org_create.html")


@login_required
def members(request, slug):
    org = get_object_or_404(Organization, slug=slug)
    members = Membership.objects.filter(organization=org)
    return render(request,"webui/members.html",{"org":org,"members":members})


@login_required
def invite_member(request, slug):
    org = get_object_or_404(Organization, slug=slug)

    if request.method == "POST":
        email = request.POST.get("email")
        role = request.POST.get("role")

        Invitation.objects.create(
            organization=org,
            email=email,
            role=role,
            invited_by=request.user
        )

        messages.success(request,"Invitation created")
        return redirect(f"/org/{slug}/members/")

    return render(request,"webui/invite.html",{"org":org})
