from django.urls import path

from accounts import user_admin

urlpatterns = [
    path("users/", user_admin.api_users, name="api_users"),
    path("users/<int:user_id>/", user_admin.api_user_detail, name="api_user_detail"),
]
