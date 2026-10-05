from django.urls import path

from imports_app import api

urlpatterns = [
    path("import/excel/", api.api_import_excel, name="api_import_excel"),
    path("import/", api.api_import_excel, name="api_import_list"),
    path("import/<int:job_id>/", api.api_import_detail, name="api_import_detail"),
    path("import/<int:job_id>/sheet/", api.api_import_select_sheet, name="api_import_sheet"),
    path("import/<int:job_id>/preview/", api.api_import_preview, name="api_import_preview"),
    path("import/<int:job_id>/confirm/", api.api_import_confirm, name="api_import_confirm"),
    path("export/excel/", api.api_export_excel, name="api_export_excel"),
]
