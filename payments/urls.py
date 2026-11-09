from django.urls import path

from . import views

urlpatterns = [
    # POST: start paying for one of your orders
    path("orders/<str:reference>/pay/", views.OrderPayView.as_view(), name="order-pay"),
        # POST: Paystack's server notifies us about payments (signature checked)
    path("payments/paystack/webhook/", views.PaystackWebhookView.as_view(), name="paystack-webhook"),
]