from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
import json

from accounts.models import User
from tracker.models import Module, Phase, PointStatus
from tracker.permissions import can_create_point, writable_fields_for


@login_required
def register_view(request: HttpRequest) -> HttpResponse:
    phases = Phase.objects.filter(is_active=True).order_by("sort_order")
    modules = Module.objects.filter(is_active=True).order_by("name")
    owners = User.objects.filter(
        is_active=True,
        role__in=[User.Role.FORBMAX_ADMIN, User.Role.FORBMAX_MEMBER],
    )
    writable = sorted(writable_fields_for(request.user))
    return render(
        request,
        "tracker/register.html",
        {
            "phases": phases,
            "modules": modules,
            "statuses": PointStatus.choices,
            "owners": owners,
            "can_create": can_create_point(request.user),
            "writable_fields_json": json.dumps(writable),
            "is_nimar": request.user.is_nimar,
            "is_forbmax": request.user.is_forbmax,
        },
    )
