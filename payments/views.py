import json

from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from . import paystack
from .serializers import PaymentSerializer
from .services import confirm_payment, start_payment


# POST /api/v1/orders/<reference>/pay/ : start paying for one of your pending orders
class OrderPayView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer
    lookup_field = "reference"

    def get_queryset(self):
        # Only your own orders; anyone else's reference is a 404
        return Order.objects.filter(buyer=self.request.user)

    def post(self, request, *args, **kwargs):
        order = self.get_object()
        payment = start_payment(order)  # the rules, the lock, and the Paystack call
        return Response(self.get_serializer(payment).data)

# POST /api/v1/payments/paystack/webhook/ : Paystack's server tells us about payments
class PaystackWebhookView(APIView):
    authentication_classes = []                  # Paystack doesn't log in...
    permission_classes = [permissions.AllowAny]  # ...the signature proves who it is

    def post(self, request):
        # 1. Read the exact bytes Paystack sent, before anything parses them
        raw_body = request.body
        signature = request.headers.get("x-paystack-signature", "")

        # 2. No valid seal, no deal
        if not paystack.is_valid_signature(raw_body, signature):
            return Response({"detail": "Invalid signature."}, status=400)

        # 3. Genuine: read the message and act on the events we care about
        event = json.loads(raw_body)
        if event.get("event") == "charge.success":
            confirm_payment(event.get("data", {}))

        # 4. Reply 200 quickly: tells Paystack "received, stop resending"
        return Response({"received": True})