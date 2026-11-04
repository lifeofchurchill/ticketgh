from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    # /api/v1/auth/register/ -> sign up with email and password
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    # /api/v1/auth/token/ -> log in: email + password in, access + refresh tokens out
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    # /api/v1/auth/token/refresh/ -> refresh token in, new access token out
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # /api/v1/auth/me/ -> view or edit your own profile (login required)
    path("auth/me/", views.MeView.as_view(), name="me"),
]