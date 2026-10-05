from django.urls import path

from config.health import health_check

urlpatterns = [
    path("", health_check, name="health"),
]
