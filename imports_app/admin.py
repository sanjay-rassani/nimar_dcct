from django.contrib import admin

from imports_app.models import ImportJob


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "status",
        "sheet_name",
        "uploaded_by",
        "total_rows",
        "created_count",
        "updated_count",
        "failed_count",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("original_filename", "sheet_name")
    raw_id_fields = ("uploaded_by",)
    readonly_fields = (
        "analysis",
        "preview_summary",
        "error_summary",
        "column_mapping",
        "status_mapping",
        "phase_mapping",
        "created_at",
        "updated_at",
        "completed_at",
    )
