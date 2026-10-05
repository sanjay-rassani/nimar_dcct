from django.urls import path

from accounts import user_admin, views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("users/", user_admin.users_page, name="users"),
    path("home/", views.home_view, name="home"),
]
