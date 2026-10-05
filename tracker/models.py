from django.conf import settings
from django.db import models


class Phase(models.Model):
    """Configurable delivery phases: Demo Day, 25%, 75%, SLA."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Module(models.Model):
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PointStatus(models.TextChoices):
    PLANNED = "PLANNED", "Planned"
    SCOPE_APPROVAL = "SCOPE_APPROVAL", "Scope Approval"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION", "Awaiting Verification"
    REWORK_REQUESTED = "REWORK_REQUESTED", "Rework Requested"
    VERIFIED_CLOSED = "VERIFIED_CLOSED", "Verified & Closed"


class Point(models.Model):
    """Central delivery-point business object."""

    external_id = models.CharField(max_length=64, unique=True, db_index=True)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.PROTECT,
        related_name="points",
        null=True,
        blank=True,
    )
    annexure = models.CharField(max_length=32, blank=True)
    number = models.CharField(max_length=64, blank=True)
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name="points",
        null=True,
        blank=True,
    )
    phase = models.ForeignKey(
        Phase,
        on_delete=models.PROTECT,
        related_name="points",
        null=True,
        blank=True,
    )
    # Annexure "Requirement" / Finding cells are often full paragraphs.
    title = models.TextField(blank=True)
    requirement = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=PointStatus.choices,
        default=PointStatus.PLANNED,
        db_index=True,
    )
    forbmax_response = models.TextField(blank=True)
    nimar_response = models.TextField(blank=True)
    decision = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_points",
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    # Preserve unmapped spreadsheet columns during migration
    source_metadata = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    scope_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_points",
    )

    class Meta:
        ordering = ["external_id"]
        indexes = [
            models.Index(fields=["phase", "status"]),
            models.Index(fields=["module", "status"]),
            models.Index(fields=["owner", "due_date"]),
        ]

    def __str__(self) -> str:
        return self.external_id


class IssueStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ACKNOWLEDGED = "ACKNOWLEDGED", "Acknowledged"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


class Issue(models.Model):
    point = models.ForeignKey(Point, on_delete=models.CASCADE, related_name="issues")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=IssueStatus.choices,
        default=IssueStatus.OPEN,
        db_index=True,
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="raised_issues",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_issues",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_issues",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["point", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.point.external_id}: {self.title}"


class Comment(models.Model):
    point = models.ForeignKey(
        Point,
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
    )
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comments",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author_id} at {self.created_at}"


class Attachment(models.Model):
    class AttachmentType(models.TextChoices):
        FILE = "FILE", "File"
        URL = "URL", "URL"
        SCOPE = "SCOPE", "Scope"
        VERIFICATION = "VERIFICATION", "Verification"
        OTHER = "OTHER", "Other"

    point = models.ForeignKey(
        Point,
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="attachments",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=255)
    file = models.FileField(upload_to="evidence/%Y/%m/", blank=True, null=True)
    url = models.URLField(blank=True)
    attachment_type = models.CharField(
        max_length=32,
        choices=AttachmentType.choices,
        default=AttachmentType.OTHER,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.label
