from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Order
from .serializers import OrderCreateSerializer, OrderSerializer
from .services import reserve_tickets


# GET  /api/v1/orders/ : the logged-in user's own orders, newest first
# POST /api/v1/orders/ : reserve tickets for 10 minutes
class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]  # must be logged in
    serializer_class = OrderSerializer                  # the shape of orders going out

    def get_queryset(self):
        # Only your own orders, with their lines and ticket names fetched up front
        return Order.objects.filter(buyer=self.request.user).prefetch_related("items__ticket_type")

    def create(self, request, *args, **kwargs):
        # 1. Check the shape of what was sent
        input_serializer = OrderCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        # 2. Apply the business rules and save, inside one locked transaction
        order = reserve_tickets(request.user, input_serializer.validated_data["items"])

        # 3. Reply with the new order
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


# GET /api/v1/orders/<reference>/ : one of your own orders
class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = "reference"  # find orders by reference, not ID

    def get_queryset(self):
        # Someone else's order is simply not found (404)
        return Order.objects.filter(buyer=self.request.user).prefetch_related("items__ticket_type")