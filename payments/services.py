from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from orders.models import Order

from . import paystack
from .models import Payment


# Raised when Paystack can't help right now (502 Bad Gateway)
class PaymentUnavailable(APIException):
    status_code = 502
    default_detail = "Payments are temporarily unavailable. Please try again."
    default_code = "payment_unavailable"


@transaction.atomic
def start_payment(order):
    # Lock this order: if Pay is tapped twice at once, the second tap waits for the first
    order = Order.objects.select_for_update().get(pk=order.pk)

    # Rules: only pending orders whose hold hasn't run out can be paid
    if order.status != Order.Status.PENDING:
        raise ValidationError("This order can no longer be paid.")
    if order.expires_at <= timezone.now():
        raise ValidationError("This reservation has expired. Please reserve again.")

    # Pressed Pay twice? Hand back the payment page we already have
    existing = order.payments.filter(status=Payment.Status.INITIALIZED).first()
    if existing:
        return existing

    # A new attempt: TGH-7KQ2M9XA-1, then -2 if that one failed, and so on
    attempt = order.payments.count() + 1
    reference = f"{order.reference}-{attempt}"

    try:
        data = paystack.initialize_transaction(
            email=order.buyer.email,
            amount=order.total,
            reference=reference,
        )
    except paystack.PaystackError as error:
        raise PaymentUnavailable() from error

    return Payment.objects.create(
        order=order,
        reference=reference,
        amount=order.total,
        authorization_url=data["authorization_url"],
        provider_response=data,
    )