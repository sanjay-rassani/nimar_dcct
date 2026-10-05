from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """Immutable lightweight activity / audit trail."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=64)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["entity_type", "entity_id", "created_at"]),
        ]
        verbose_name = "Activity log"
        verbose_name_plural = "Activity logs"

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.entity_id} {self.action}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("ActivityLog entries are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ActivityLog entries are immutable and cannot be deleted.")
