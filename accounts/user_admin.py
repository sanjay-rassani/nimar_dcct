import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import Organization, User
from accounts.permissions import forbmax_admin_required


def _error(exc, status=400):
    if hasattr(exc, "message_dict"):
        return JsonResponse({"detail": exc.message_dict}, status=status)
    if hasattr(exc, "messages"):
        return JsonResponse({"detail": list(exc.messages)}, status=status)
    return JsonResponse({"detail": str(exc)}, status=status)


def user_dict(user: User) -> dict:
    return {
        "id": user.pk,
        "name": user.name,
        "email": user.email,
        "organization": user.organization.name if user.organization_id else None,
        "organization_code": user.organization.code if user.organization_id else None,
        "role": user.role,
        "role_label": user.get_role_display(),
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


@forbmax_admin_required
def users_page(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "accounts/users.html",
        {
            "roles": User.Role.choices,
            "organizations": Organization.objects.filter(is_active=True),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def api_users(request: HttpRequest):
    if not (request.user.is_forbmax_admin or request.user.is_superuser):
        return JsonResponse({"detail": "Only Forbmax Admin can manage users."}, status=403)

    if request.method == "GET":
        users = User.objects.select_related("organization").order_by("name")
        return JsonResponse({"results": [user_dict(u) for u in users]})

    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)

    try:
        with transaction.atomic():
            email = (payload.get("email") or "").strip().lower()
            name = (payload.get("name") or "").strip()
            role = payload.get("role")
            org_code = payload.get("organization_code")
            password = payload.get("password") or "ChangeMe123!"

            if not email or not name or not role:
                raise ValidationError("name, email, and role are required.")
            if role not in User.Role.values:
                raise ValidationError("Invalid role.")
            if User.objects.filter(email=email).exists():
                raise ValidationError({"email": "A user with this email already exists."})

            if role in {User.Role.FORBMAX_ADMIN, User.Role.FORBMAX_MEMBER}:
                org = Organization.objects.get(code=Organization.Code.FORBMAX)
            else:
                org = Organization.objects.get(code=Organization.Code.NIMAR)
            if org_code:
                org = Organization.objects.get(code=org_code)

            user = User(
                email=email,
                name=name,
                role=role,
                organization=org,
                is_active=True,
                is_staff=role == User.Role.FORBMAX_ADMIN,
            )
            user.set_password(password)
            user.full_clean()
            user.save()
            return JsonResponse(user_dict(user), status=201)
    except Organization.DoesNotExist:
        return JsonResponse({"detail": "Organization not found."}, status=400)
    except ValidationError as exc:
        return _error(exc)


@login_required
@require_http_methods(["PATCH"])
def api_user_detail(request: HttpRequest, user_id: int):
    if not (request.user.is_forbmax_admin or request.user.is_superuser):
        return JsonResponse({"detail": "Only Forbmax Admin can manage users."}, status=403)

    user = get_object_or_404(User, pk=user_id)
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)

    try:
        if "name" in payload:
            user.name = (payload.get("name") or "").strip()
        if "role" in payload:
            role = payload["role"]
            if role not in User.Role.values:
                raise ValidationError("Invalid role.")
            user.role = role
            user.is_staff = role == User.Role.FORBMAX_ADMIN
            if role in {User.Role.FORBMAX_ADMIN, User.Role.FORBMAX_MEMBER}:
                user.organization = Organization.objects.get(code=Organization.Code.FORBMAX)
            else:
                user.organization = Organization.objects.get(code=Organization.Code.NIMAR)
        if "is_active" in payload:
            user.is_active = bool(payload["is_active"])
            if user.pk == request.user.pk and not user.is_active:
                raise ValidationError("You cannot deactivate your own account.")
        if payload.get("password"):
            user.set_password(payload["password"])
        user.full_clean()
        user.save()
        return JsonResponse(user_dict(user))
    except ValidationError as exc:
        return _error(exc)
