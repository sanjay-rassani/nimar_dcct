from django.urls import path

from tracker import api, views, views_extra

app_name = "tracker"

urlpatterns = [
    path("points/", views.register_view, name="register"),
    path("kanban/", views_extra.kanban_view, name="kanban"),
    path("timeline/", views_extra.timeline_view, name="timeline"),
]
