from django.urls import path

from . import views

urlpatterns = [
    # /api/v1/auth/register/ -> sign up with email and password
    path("auth/register/", views.RegisterView.as_view(), name="register"),
]