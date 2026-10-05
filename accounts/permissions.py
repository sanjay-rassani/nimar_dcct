from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from accounts.models import User


def role_required(*roles: str):
    """Backend authorization gate — frontend hiding is never enough."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            user: User = request.user  # type: ignore[assignment]
            if not user.is_active:
                raise PermissionDenied("Inactive users cannot access this resource.")
            if user.role not in roles and not user.is_superuser:
                raise PermissionDenied("You do not have permission to perform this action.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def forbmax_required(view_func):
    return role_required(User.Role.FORBMAX_ADMIN, User.Role.FORBMAX_MEMBER)(view_func)


def forbmax_admin_required(view_func):
    return role_required(User.Role.FORBMAX_ADMIN)(view_func)


def organization_scoped_queryset(user: User, queryset, org_field: str = "organization"):
    """
    Restrict querysets by organization.
    Forbmax can see all operational data; NIMAR sees client-safe data only.
    Phase 1 lays the helper; later phases apply it to points/issues.
    """
    if user.is_superuser or user.is_forbmax:
        return queryset
    if user.is_nimar and user.organization_id:
        # NIMAR isolation: later phases filter client-visible rows;
        # for org-owned entities, scope to their organization.
        return queryset.filter(**{f"{org_field}_id": user.organization_id})
    return queryset.none()
