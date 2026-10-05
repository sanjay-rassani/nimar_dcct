import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("accounts:home")

    error = None
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_active:
            login(request, user)
            next_url = request.GET.get("next") or "metrics:dashboard"
            return redirect(next_url)
        error = "Invalid email or password."

    return render(request, "accounts/login.html", {"error": error})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("accounts:login")


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    # Role-aware landing is the dashboard (Phase 5).
    return redirect("metrics:dashboard")


@require_POST
def api_login(request: HttpRequest) -> JsonResponse:
    """POST /api/auth/login — JSON or form-encoded session login."""
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON body."}, status=400)
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
    else:
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": "Invalid email or password."}, status=401)

    login(request, user)
    return JsonResponse(
        {
            "id": user.pk,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "organization": user.organization.code if user.organization_id else None,
        }
    )


@require_POST
def api_logout(request: HttpRequest) -> JsonResponse:
    """POST /api/auth/logout"""
    logout(request)
    return JsonResponse({"detail": "Logged out."})


@login_required
@require_http_methods(["GET"])
def api_me(request: HttpRequest) -> JsonResponse:
    user = request.user
    return JsonResponse(
        {
            "id": user.pk,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "organization": user.organization.code if user.organization_id else None,
            "is_active": user.is_active,
        }
    )
