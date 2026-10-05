from django.conf import settings
from django.db import models


class ImportJob(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        ANALYZED = "ANALYZED", "Analyzed"
        VALIDATED = "VALIDATED", "Validated"
        PREVIEWED = "PREVIEWED", "Previewed"
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    file = models.FileField(upload_to="imports/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="import_jobs",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.UPLOADED)
    sheet_name = models.CharField(max_length=255, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    column_mapping = models.JSONField(default=dict, blank=True)
    status_mapping = models.JSONField(default=dict, blank=True)
    phase_mapping = models.JSONField(default=dict, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    preview_summary = models.JSONField(default=dict, blank=True)
    error_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ImportJob {self.pk} ({self.original_filename})"
