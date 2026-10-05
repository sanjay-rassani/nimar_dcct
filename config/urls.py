from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("config.health_urls")),
    path("", include("metrics.urls")),
    path("", include("accounts.urls")),
    path("", include("tracker.urls")),
    path("", include("imports_app.urls")),
    path("api/auth/", include("accounts.api_urls")),
    path("api/", include("accounts.user_api_urls")),
    path("api/", include("tracker.api_urls")),
    path("api/", include("imports_app.api_urls")),
    path("api/", include("metrics.api_urls")),
]
