from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import ProtectedError
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