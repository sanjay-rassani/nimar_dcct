from django.contrib import admin

from accounts.models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    list_filter = ("is_active", "code")
    search_fields = ("name", "code")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "organization", "role", "is_active", "is_staff")
    list_filter = ("role", "organization", "is_active", "is_staff")
    search_fields = ("email", "name")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name", "organization", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
