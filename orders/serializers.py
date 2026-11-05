from rest_framework import serializers

from .models import Order, OrderItem


# One requested line, as sent by the app: which ticket type, how many
class OrderItemInputSerializer(serializers.Serializer):
    ticket_type = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=10)


# The whole reservation request: a list of lines (at least one)
class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(many=True, allow_empty=False)


# One line of an order, as sent back to the app
class OrderItemSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source="ticket_type.name", read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["ticket_type", "ticket_type_name", "quantity", "unit_price", "subtotal"]


# A whole order, as sent back to the app
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["reference", "status", "total", "expires_at", "created_at", "items"]