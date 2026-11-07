from rest_framework import generics, permissions
from rest_framework.response import Response

from orders.models import Order

from .serializers import PaymentSerializer
from .services import start_payment


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