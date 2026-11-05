from django.urls import path

from . import views

urlpatterns = [
    # GET: your orders / POST: reserve tickets
    path("orders/", views.OrderListCreateView.as_view(), name="order-list"),
    # GET: one of your orders, by reference
    path("orders/<str:reference>/", views.OrderDetailView.as_view(), name="order-detail"),
]