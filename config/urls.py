from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),    # /api/v1/health/
    path("api/v1/", include("users.urls")),   # /api/v1/auth/register/
    path("api/v1/", include("events.urls")),  # /api/v1/events/
    path("api/v1/", include("orders.urls")),  # /api/v1/orders/...
]