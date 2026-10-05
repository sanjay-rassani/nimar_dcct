from django.contrib import admin

from audit.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "organization", "entity_type", "entity_id", "action")
    list_filter = ("entity_type", "action", "organization")
    search_fields = ("entity_id", "action", "message")
    readonly_fields = (
        "actor",
        "organization",
        "entity_type",
        "entity_id",
        "action",
        "old_value",
        "new_value",
        "message",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
