from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "metrics/dashboard.html",
        {
            "is_nimar": request.user.is_nimar,
            "is_forbmax": request.user.is_forbmax,
            "is_forbmax_admin": request.user.is_forbmax_admin or request.user.is_superuser,
        },
    )


@login_required
def metrics_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "metrics/metrics.html",
        {
            "is_nimar": request.user.is_nimar,
            "is_forbmax": request.user.is_forbmax,
        },
    )
