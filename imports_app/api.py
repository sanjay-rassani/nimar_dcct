import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods

from imports_app.export import export_points_xlsx
from imports_app.models import ImportJob
from imports_app.services import (
    build_preview,
    confirm_import,
    create_import_job,
    job_to_dict,
    select_sheet,
)


def _error_response(exc: ValidationError, status: int = 400) -> JsonResponse:
    if hasattr(exc, "message_dict"):
        return JsonResponse({"detail": exc.message_dict}, status=status)
    if hasattr(exc, "messages"):
        return JsonResponse({"detail": list(exc.messages)}, status=status)
    return JsonResponse({"detail": str(exc)}, status=status)


def _json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid JSON body.") from exc
    if not isinstance(data, dict):
        raise ValidationError("JSON body must be an object.")
    return data


def _require_forbmax(user):
    if not user.is_authenticated or not (user.is_forbmax or user.is_superuser):
        return JsonResponse({"detail": "Only Forbmax users can manage imports/exports."}, status=403)
    return None


@login_required
@require_http_methods(["GET", "POST"])
def api_import_excel(request: HttpRequest):
    if err := _require_forbmax(request.user):
        return err

    if request.method == "GET":
        qs = ImportJob.objects.select_related("uploaded_by").order_by("-created_at")
        return JsonResponse(
            {
                "results": [job_to_dict(j) for j in qs[:50]],
                "count": qs.count(),
            }
        )

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"detail": "No file uploaded. Send multipart field 'file'."}, status=400)
    try:
        job = create_import_job(actor=request.user, uploaded_file=uploaded)
        return JsonResponse(job_to_dict(job), status=201)
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_GET
def api_import_detail(request: HttpRequest, job_id: int):
    if err := _require_forbmax(request.user):
        return err
    job = get_object_or_404(ImportJob.objects.select_related("uploaded_by"), pk=job_id)
    return JsonResponse(job_to_dict(job))


@login_required
@require_http_methods(["POST"])
def api_import_select_sheet(request: HttpRequest, job_id: int):
    if err := _require_forbmax(request.user):
        return err
    job = get_object_or_404(ImportJob, pk=job_id)
    try:
        payload = _json_body(request)
        sheet = payload.get("sheet_name") or payload.get("sheet")
        if not sheet:
            return JsonResponse({"detail": "sheet_name is required."}, status=400)
        job = select_sheet(job=job, sheet_name=sheet)
        return JsonResponse(job_to_dict(job))
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_http_methods(["POST"])
def api_import_preview(request: HttpRequest, job_id: int):
    if err := _require_forbmax(request.user):
        return err
    job = get_object_or_404(ImportJob, pk=job_id)
    try:
        payload = _json_body(request)
        job = build_preview(
            job=job,
            column_mapping=payload.get("column_mapping"),
            status_mapping=payload.get("status_mapping"),
            phase_mapping=payload.get("phase_mapping"),
        )
        return JsonResponse(job_to_dict(job))
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_http_methods(["POST"])
def api_import_confirm(request: HttpRequest, job_id: int):
    if err := _require_forbmax(request.user):
        return err
    job = get_object_or_404(ImportJob, pk=job_id)
    try:
        job = confirm_import(job=job, actor=request.user)
        return JsonResponse(job_to_dict(job))
    except ValidationError as exc:
        return _error_response(exc)


@login_required
@require_GET
def api_export_excel(request: HttpRequest):
    if err := _require_forbmax(request.user):
        return err
    content = export_points_xlsx(request.GET)
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = "nimar_points_export.xlsx"
    if phase := request.GET.get("phase"):
        filename = f"nimar_points_{phase}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
