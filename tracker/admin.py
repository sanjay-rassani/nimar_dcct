from django.contrib import admin

from tracker.models import Attachment, Comment, Issue, Module, Phase, Point


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort_order", "is_active", "start_date", "end_date")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("sort_order",)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Point)
class PointAdmin(admin.ModelAdmin):
    list_display = (
        "external_id",
        "module",
        "phase",
        "status",
        "owner",
        "due_date",
        "updated_at",
    )
    list_filter = ("status", "phase", "module", "annexure")
    search_fields = ("external_id", "title", "requirement", "remarks")
    raw_id_fields = ("owner", "updated_by", "organization")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("id", "point", "title", "status", "raised_by", "assigned_to", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "description", "point__external_id")
    raw_id_fields = ("point", "raised_by", "assigned_to", "resolved_by")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "point", "issue", "created_at")
    search_fields = ("message",)
    raw_id_fields = ("author", "point", "issue")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("label", "attachment_type", "point", "issue", "uploaded_by", "created_at")
    list_filter = ("attachment_type",)
    search_fields = ("label", "url")
    raw_id_fields = ("uploaded_by", "point", "issue", "comment")
