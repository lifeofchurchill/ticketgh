from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from django.utils.dateparse import parse_datetime
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

@transaction.atomic
def confirm_payment(data):
    # data is the "data" part of Paystack's charge.success webhook

    # Find our payment attempt, and lock it so two copies of the message can't both run
    payment = Payment.objects.select_for_update().filter(reference=data.get("reference")).first()
    if payment is None:
        return "unknown_reference"   # not one of ours: nothing to do
    if payment.status == Payment.Status.SUCCESS:
        return "already_processed"   # Paystack sent it again: nothing to do

    payment.provider_response = data  # keep Paystack's exact words, for audits

    # Rule: the money must match, to the pesewa, in cedis
    if data.get("currency") != "GHS" or data.get("amount") != paystack.to_pesewas(payment.amount):
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "provider_response", "updated_at"])
        return "amount_mismatch"

    payment.status = Payment.Status.SUCCESS
    payment.save(update_fields=["status", "provider_response", "updated_at"])

    # Now decide what happens to the order
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == Order.Status.PAID:
        return "duplicate_payment"   # already paid by another attempt: staff refund this one

    # When did the buyer actually pay? Paystack tells us; fall back to "now"
    paid_at = parse_datetime(data.get("paid_at") or "") or timezone.now()

    if order.status == Order.Status.PENDING and paid_at <= order.expires_at:
        order.status = Order.Status.PAID            # paid in time: the tickets are theirs
        result = "paid"
    else:
        order.status = Order.Status.REFUND_PENDING  # paid too late, or the event was cancelled
        result = "refund_pending"
    order.save(update_fields=["status", "updated_at"])
    return result