from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from accounts.permissions import forbmax_required


@forbmax_required
def import_page(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "imports_app/import.html",
        {
            "is_forbmax_admin": request.user.is_forbmax_admin or request.user.is_superuser,
        },
    )
