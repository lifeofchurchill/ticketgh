from django.urls import path

from . import views

urlpatterns = [
    # POST: start paying for one of your orders
    path("orders/<str:reference>/pay/", views.OrderPayView.as_view(), name="order-pay"),
]