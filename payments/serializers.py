from rest_framework import serializers

from .models import Payment


# What the app needs to send the buyer to Paystack
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["reference", "amount", "status", "authorization_url"]