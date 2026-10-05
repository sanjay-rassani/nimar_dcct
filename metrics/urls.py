from django.urls import path

from metrics import views

app_name = "metrics"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("metrics/", views.metrics_view, name="metrics"),
]
