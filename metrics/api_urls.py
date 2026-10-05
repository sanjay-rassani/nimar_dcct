from django.urls import path

from metrics import api

urlpatterns = [
    path("metrics/overview/", api.api_metrics_overview, name="api_metrics_overview"),
    path("metrics/phases/", api.api_metrics_phases, name="api_metrics_phases"),
    path("metrics/modules/", api.api_metrics_modules, name="api_metrics_modules"),
    path("metrics/issues/", api.api_metrics_issues, name="api_metrics_issues"),
    path("metrics/trends/", api.api_metrics_trends, name="api_metrics_trends"),
    path("dashboard/", api.api_dashboard, name="api_dashboard"),
]
