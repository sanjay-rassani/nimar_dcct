from django.urls import path

from accounts import views

urlpatterns = [
    path("login/", views.api_login, name="api_auth_login"),
    path("logout/", views.api_logout, name="api_auth_logout"),
    path("me/", views.api_me, name="api_auth_me"),
]
