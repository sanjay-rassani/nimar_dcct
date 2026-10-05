from django.urls import path

from tracker import api, collaboration_api, views_extra

urlpatterns = [
    path("points/", api.api_points_list, name="api_points_list"),
    path("points/<int:point_id>/", api.api_point_detail, name="api_point_detail"),
    path("points/<int:point_id>/history/", collaboration_api.api_point_history, name="api_point_history"),
    path("points/<int:point_id>/comments/", collaboration_api.api_point_comments, name="api_point_comments"),
    path("points/<int:point_id>/attachments/", collaboration_api.api_point_attachments, name="api_point_attachments"),
    path("issues/", collaboration_api.api_issues_list, name="api_issues_list"),
    path("issues/<int:issue_id>/", collaboration_api.api_issue_detail, name="api_issue_detail"),
    path("issues/<int:issue_id>/comments/", collaboration_api.api_issue_comments, name="api_issue_comments"),
    path("issues/<int:issue_id>/attachments/", collaboration_api.api_issue_attachments, name="api_issue_attachments"),
    path("register/summary/", collaboration_api.api_register_summary, name="api_register_summary"),
    path("kanban/", views_extra.api_kanban, name="api_kanban"),
    path("timeline/", views_extra.api_timeline, name="api_timeline"),
    path("phases/", api.api_phases, name="api_phases"),
    path("modules/", api.api_modules, name="api_modules"),
    path("statuses/", api.api_statuses, name="api_statuses"),
    path("owners/", api.api_owners, name="api_owners"),
]
