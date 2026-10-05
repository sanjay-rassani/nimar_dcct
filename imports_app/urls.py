from django.urls import path

from imports_app import views

app_name = "imports_app"

urlpatterns = [
    path("import/", views.import_page, name="import"),
]
