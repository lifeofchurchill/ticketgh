import hashlib
import hmac
import json

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order, OrderItem
from payments import paystack
from payments.models import Payment

# Every test in this file may use the (temporary) test database
pytestmark = pytest.mark.django_db

# What our fake Paystack replies when asked to start a payment
FAKE_PAYSTACK_DATA = {
    "authorization_url": "https://checkout.paystack.com/fake123",
    "access_code": "fake123",
    "reference": "ignored-in-tests",
}

# The function our tests replace with a fake
INITIALIZE = "payments.paystack.initialize_transaction"


@pytest.fixture
def pending_order(organizer, attendee):
    # The attendee holds 2 VIP tickets (GHS 1,000 total), still inside the 10 minutes
    start = timezone.now() + timedelta(days=30)
    event = Event.objects.create(
        organizer=organizer, title="Summit", slug="summit", venue_name="AICC",
        city="Accra", starts_at=start, ends_at=start + timedelta(hours=8),
        status=Event.Status.PUBLISHED,
    )
    vip = TicketType.objects.create(event=event, name="VIP", price="500.00", quantity=50)
    order = Order.objects.create(buyer=attendee, total=Decimal("1000.00"))
    OrderItem.objects.create(order=order, ticket_type=vip, quantity=2, unit_price=vip.price)
    return order


def pay(api_client, order):
    # Helper: tap "Pay" for this order
    return api_client.post(reverse("order-pay", kwargs={"reference": order.reference}))


def test_to_pesewas_converts_exactly():
    assert paystack.to_pesewas(Decimal("500.00")) == 50000
    assert paystack.to_pesewas(Decimal("29.99")) == 2999


def test_pay_starts_a_paystack_payment(api_client, attendee, pending_order):
    api_client.force_authenticate(user=attendee)

    # Replace the real Paystack call with a fake that returns FAKE_PAYSTACK_DATA
    with patch(INITIALIZE, return_value=FAKE_PAYSTACK_DATA) as fake_initialize:
        response = pay(api_client, pending_order)

    assert response.status_code == 200
    assert response.data["authorization_url"] == "https://checkout.paystack.com/fake123"
    assert response.data["reference"] == f"{pending_order.reference}-1"

    # We asked "Paystack" exactly once, for the right person and amount
    fake_initialize.assert_called_once()
    sent = fake_initialize.call_args.kwargs
    assert sent["email"] == attendee.email
    assert sent["amount"] == Decimal("1000.00")

    # The attempt was recorded
    payment = Payment.objects.get(order=pending_order)
    assert payment.amount == Decimal("1000.00")
    assert payment.status == Payment.Status.INITIALIZED


def test_pressing_pay_twice_reuses_the_same_payment(api_client, attendee, pending_order):
    api_client.force_authenticate(user=attendee)

    with patch(INITIALIZE, return_value=FAKE_PAYSTACK_DATA) as fake_initialize:
        first = pay(api_client, pending_order)
        second = pay(api_client, pending_order)

    assert first.data["reference"] == second.data["reference"]
    fake_initialize.assert_called_once()           # Paystack was only asked once
    assert Payment.objects.count() == 1            # one attempt, not two


def test_cannot_pay_an_expired_reservation(api_client, attendee, pending_order):
    pending_order.expires_at = timezone.now() - timedelta(minutes=1)
    pending_order.save()
    api_client.force_authenticate(user=attendee)

    with patch(INITIALIZE) as fake_initialize:
        response = pay(api_client, pending_order)

    assert response.status_code == 400
    fake_initialize.assert_not_called()            # we didn't even ask Paystack


def test_cannot_pay_someone_elses_order(api_client, organizer, pending_order):
    api_client.force_authenticate(user=organizer)  # not the buyer

    with patch(INITIALIZE) as fake_initialize:
        response = pay(api_client, pending_order)

    assert response.status_code == 404
    fake_initialize.assert_not_called()


def test_paystack_being_down_gives_502_and_saves_nothing(api_client, attendee, pending_order):
    api_client.force_authenticate(user=attendee)

    # side_effect: instead of returning something, the fake raises this error
    with patch(INITIALIZE, side_effect=paystack.PaystackError("Could not reach Paystack.")):
        response = pay(api_client, pending_order)

    assert response.status_code == 502
    assert Payment.objects.count() == 0            # nothing half-saved

# ---------- The webhook ----------

TEST_SECRET = "sk_test_fake_secret"


@pytest.fixture(autouse=True)
def fake_paystack_secret(settings):
    # Every test in this file uses a known, fake secret key
    settings.PAYSTACK_SECRET_KEY = TEST_SECRET


@pytest.fixture
def payment(pending_order):
    # A payment attempt that Paystack has been asked to collect
    return Payment.objects.create(
        order=pending_order,
        reference=f"{pending_order.reference}-1",
        amount=pending_order.total,
    )


def charge_success(payment, amount=None, paid_at=None):
    # A Paystack-style charge.success message for this payment
    return {
        "event": "charge.success",
        "data": {
            "reference": payment.reference,
            "amount": amount if amount is not None else paystack.to_pesewas(payment.amount),
            "currency": "GHS",
            "status": "success",
            "paid_at": (paid_at or timezone.now()).isoformat(),
        },
    }


def send_webhook(api_client, message, signature=None):
    # Send the message the way Paystack does: raw JSON bytes plus a signature header
    body = json.dumps(message).encode()
    if signature is None:
        signature = hmac.new(TEST_SECRET.encode(), body, hashlib.sha512).hexdigest()
    return api_client.post(
        reverse("paystack-webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=signature,
    )


def test_genuine_webhook_marks_the_order_paid(api_client, payment):
    response = send_webhook(api_client, charge_success(payment))

    assert response.status_code == 200
    payment.refresh_from_db()
    payment.order.refresh_from_db()
    assert payment.status == Payment.Status.SUCCESS
    assert payment.order.status == Order.Status.PAID
    assert payment.provider_response["reference"] == payment.reference  # Paystack's words kept


def test_forged_signature_is_rejected(api_client, payment):
    response = send_webhook(api_client, charge_success(payment), signature="forged-by-kwame")

    assert response.status_code == 400
    payment.order.refresh_from_db()
    assert payment.order.status == Order.Status.PENDING  # nothing changed


def test_same_webhook_twice_is_harmless(api_client, payment):
    message = charge_success(payment)

    first = send_webhook(api_client, message)
    second = send_webhook(api_client, message)

    assert first.status_code == 200
    assert second.status_code == 200  # acknowledged, so Paystack stops resending
    payment.order.refresh_from_db()
    assert payment.order.status == Order.Status.PAID
    assert Payment.objects.filter(status=Payment.Status.SUCCESS).count() == 1


def test_wrong_amount_does_not_mark_the_order_paid(api_client, payment):
    response = send_webhook(api_client, charge_success(payment, amount=100))  # GHS 1.00

    assert response.status_code == 200
    payment.refresh_from_db()
    payment.order.refresh_from_db()
    assert payment.status == Payment.Status.FAILED
    assert payment.order.status == Order.Status.PENDING


def test_payment_after_the_deadline_goes_to_refund(api_client, payment):
    too_late = payment.order.expires_at + timedelta(minutes=5)

    send_webhook(api_client, charge_success(payment, paid_at=too_late))

    payment.order.refresh_from_db()
    assert payment.order.status == Order.Status.REFUND_PENDING


def test_delayed_webhook_for_an_on_time_payment_still_counts(api_client, payment):
    # By the time the message arrives, the deadline has already passed...
    payment.order.expires_at = timezone.now() - timedelta(minutes=1)
    payment.order.save()
    # ...but Paystack says the buyer paid one second before that deadline
    just_in_time = payment.order.expires_at - timedelta(seconds=1)

    send_webhook(api_client, charge_success(payment, paid_at=just_in_time))

    payment.order.refresh_from_db()
    assert payment.order.status == Order.Status.PAID


def test_payment_for_a_stopped_order_goes_to_refund(api_client, payment):
    # The event was cancelled while the buyer was paying, so the order was expired
    payment.order.status = Order.Status.EXPIRED
    payment.order.save()

    send_webhook(api_client, charge_success(payment))

    payment.order.refresh_from_db()
    assert payment.order.status == Order.Status.REFUND_PENDING


def test_unknown_reference_is_acknowledged_and_ignored(api_client, payment):
    message = charge_success(payment)
    message["data"]["reference"] = "SOMEONE-ELSES-REF"

    response = send_webhook(api_client, message)

    assert response.status_code == 200
    payment.order.refresh_from_db()
    assert payment.order.status == Order.Status.PENDING


def test_other_event_types_are_acknowledged(api_client, payment):
    response = send_webhook(api_client, {"event": "transfer.success", "data": {}})

    assert response.status_code == 200