from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order, OrderItem

# Every test in this file may use the (temporary) test database
pytestmark = pytest.mark.django_db


@pytest.fixture
def ticket_type(organizer):
    # A published event a month away, with 50 VIP tickets at GHS 500
    start = timezone.now() + timedelta(days=30)
    event = Event.objects.create(
        organizer=organizer,
        title="Summit",
        slug="summit",
        venue_name="AICC",
        city="Accra",
        starts_at=start,
        ends_at=start + timedelta(hours=8),
        status=Event.Status.PUBLISHED,
    )
    return TicketType.objects.create(event=event, name="VIP", price="500.00", quantity=50)


def reserve(api_client, ticket_type, quantity):
    # Helper: ask the API to reserve tickets of one type
    return api_client.post(
        reverse("order-list"),
        {"items": [{"ticket_type": ticket_type.id, "quantity": quantity}]},
        format="json",
    )


# ---------- The models (Lesson 23) ----------

def test_new_order_gets_reference_and_ten_minute_hold(attendee):
    before = timezone.now()

    order = Order.objects.create(buyer=attendee)

    assert order.reference.startswith("TGH-")
    assert len(order.reference) == 12          # "TGH-" + 8 characters
    assert order.status == Order.Status.PENDING
    # The deadline was set at creation time: 10 minutes after "now"
    assert before + timedelta(minutes=10) <= order.expires_at <= timezone.now() + timedelta(minutes=10)


def test_each_order_gets_a_different_reference(attendee):
    # Create 20 orders and collect their references in a set (duplicates collapse)
    references = {Order.objects.create(buyer=attendee).reference for _ in range(20)}

    assert len(references) == 20


def test_order_item_keeps_the_price_paid(attendee, ticket_type):
    order = Order.objects.create(buyer=attendee)
    item = OrderItem.objects.create(
        order=order, ticket_type=ticket_type, quantity=2, unit_price=ticket_type.price
    )

    # The organizer raises the price after the sale
    ticket_type.price = "650.00"
    ticket_type.save()

    item.refresh_from_db()
    assert item.unit_price == Decimal("500.00")   # the buyer's price is unchanged
    assert item.subtotal == Decimal("1000.00")    # 2 x 500.00


def test_ticket_type_with_sales_cannot_be_deleted(attendee, ticket_type):
    order = Order.objects.create(buyer=attendee)
    OrderItem.objects.create(order=order, ticket_type=ticket_type, quantity=1, unit_price=ticket_type.price)

    # PROTECT makes the delete raise an error instead of wiping the order line
    with pytest.raises(ProtectedError):
        ticket_type.delete()


# ---------- Availability ----------

def test_expired_hold_gives_tickets_back(attendee, ticket_type):
    # A pending order whose 10 minutes ran out a minute ago
    order = Order.objects.create(buyer=attendee, expires_at=timezone.now() - timedelta(minutes=1))
    OrderItem.objects.create(order=order, ticket_type=ticket_type, quantity=5, unit_price=ticket_type.price)

    assert ticket_type.available == 50  # the 5 held tickets are free again


def test_paid_tickets_stay_taken(attendee, ticket_type):
    # A paid order stays counted, even after its hold time has passed
    order = Order.objects.create(
        buyer=attendee,
        status=Order.Status.PAID,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    OrderItem.objects.create(order=order, ticket_type=ticket_type, quantity=5, unit_price=ticket_type.price)

    assert ticket_type.available == 45


# ---------- Reserving through the API ----------

def test_reserving_requires_login(api_client, ticket_type):
    response = reserve(api_client, ticket_type, 1)

    assert response.status_code == 401


def test_attendee_reserves_tickets(api_client, attendee, ticket_type):
    api_client.force_authenticate(user=attendee)

    response = reserve(api_client, ticket_type, 2)

    assert response.status_code == 201
    assert response.data["status"] == "pending"
    assert response.data["total"] == "1000.00"     # 2 x 500.00, exact
    assert ticket_type.available == 48              # 50 - 2 now held
    order = Order.objects.get(reference=response.data["reference"])
    assert order.buyer == attendee                  # buyer came from the login


def test_cannot_reserve_more_than_available(api_client, attendee, ticket_type):
    table = TicketType.objects.create(event=ticket_type.event, name="Table", price="1000.00", quantity=3)
    api_client.force_authenticate(user=attendee)

    response = reserve(api_client, table, 4)

    assert response.status_code == 409
    assert Order.objects.count() == 0  # no order was left behind


def test_cannot_reserve_tickets_for_a_draft_event(api_client, attendee, ticket_type):
    ticket_type.event.status = Event.Status.DRAFT
    ticket_type.event.save()
    api_client.force_authenticate(user=attendee)

    response = reserve(api_client, ticket_type, 1)

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_one_line_holds_at_most_ten_tickets(api_client, attendee, ticket_type):
    api_client.force_authenticate(user=attendee)

    response = reserve(api_client, ticket_type, 11)

    assert response.status_code == 400


def test_users_cannot_see_each_others_orders(api_client, attendee, organizer):
    # An order belonging to someone else
    order = Order.objects.create(buyer=organizer)
    api_client.force_authenticate(user=attendee)

    response = api_client.get(reverse("order-detail", kwargs={"reference": order.reference}))

    assert response.status_code == 404