
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Organization, Membership, Invitation, VendorAssessment, AssessmentQuestion
from .services import (
    generate_assessment_questions,
    create_assessment_for_organization,
    submit_assessment_response,
    get_next_required_controls,
)
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


# Questionnaire API Endpoints
@login_required
@require_http_methods(["GET", "POST"])
def get_assessment_questions(request, slug):
    """Get assessment questions for vendor triage."""
    try:
        org = get_object_or_404(Organization, slug=slug)
        
        # Check if user has permission
        if not Membership.objects.filter(user=request.user, organization=org).exists():
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        # Get or create assessment
        assessment = create_assessment_for_organization(org)
        
        # Get questions from database, or generate if none exist
        questions = AssessmentQuestion.objects.filter(is_active=True).order_by("order").values()
        
        if not questions.exists():
            # Generate questions if none exist
            generated = generate_assessment_questions(num_questions=5)
            for q in generated:
                AssessmentQuestion.objects.create(**q)
            questions = AssessmentQuestion.objects.filter(is_active=True).order_by("order").values()
        
        return JsonResponse({
            "success": True,
            "assessment_id": assessment.id,
            "status": assessment.status,
            "questions": list(questions),
        })
    
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_http_methods(["POST"])
def submit_assessment(request, slug):
    """Submit assessment responses."""
    try:
        import json
        
        org = get_object_or_404(Organization, slug=slug)
        
        # Check permission
        if not Membership.objects.filter(user=request.user, organization=org).exists():
            return JsonResponse({"error": "Permission denied"}, status=403)
        
        data = json.loads(request.body)
        responses = data.get("responses", {})
        
        # Get assessment
        assessment = VendorAssessment.objects.get(organization=org)
        
        # Submit responses
        assessment = submit_assessment_response(assessment, responses)
        
        # Get required controls
        controls = get_next_required_controls(org)
        control_data = [
            {
                "id": c.id,
                "code": c.code,
                "title": c.title_en,
                "risk_level": c.risk_level,
            }
            for c in controls
        ]
        
        return JsonResponse({
            "success": True,
            "vendor_type": assessment.vendor_type_determined,
            "risk_score": assessment.risk_score,
            "required_controls": control_data,
        })
    
    except VendorAssessment.DoesNotExist:
        return JsonResponse({"error": "Assessment not found"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
