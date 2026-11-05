from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from events.models import Event, TicketType

from .models import Order, OrderItem

# Spec rule 7: one order can hold at most 10 tickets
MAX_TICKETS_PER_ORDER = 10


# Raised when someone asks for more tickets than remain (409 Conflict)
class SoldOut(APIException):
    status_code = 409
    default_detail = "Not enough tickets left."
    default_code = "sold_out"


@transaction.atomic  # everything below succeeds together, or is undone together
def reserve_tickets(buyer, items):
    # items looks like: [{"ticket_type": 1, "quantity": 2}, {"ticket_type": 2, "quantity": 1}]

    # Rule: at most 10 tickets in one order
    total_quantity = sum(item["quantity"] for item in items)
    if total_quantity > MAX_TICKETS_PER_ORDER:
        raise ValidationError(f"One order can hold at most {MAX_TICKETS_PER_ORDER} tickets.")

    # Rule: each ticket type appears once (send quantity 3, not three lines of 1)
    ids = [item["ticket_type"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValidationError("Each ticket type can appear only once in an order.")

    # LOCK: fetch these ticket types and lock their rows until this transaction ends.
    # Anyone else trying to lock the same rows waits here until we finish.
    ticket_types = {
        tt.id: tt
        for tt in TicketType.objects.select_for_update(of=("self",))
        .select_related("event")
        .filter(id__in=ids)
        .order_by("id")  # always lock in the same order, to avoid deadlocks
    }
    if len(ticket_types) != len(ids):
        raise ValidationError("One or more ticket types do not exist.")

    # Rule: one order is for one event
    if len({tt.event_id for tt in ticket_types.values()}) > 1:
        raise ValidationError("All tickets in an order must be for the same event.")

    # Check every line BEFORE writing anything
    now = timezone.now()
    for item in items:
        tt = ticket_types[item["ticket_type"]]
        if tt.event.status != Event.Status.PUBLISHED or tt.event.starts_at <= now:
            raise ValidationError(f"{tt.event.title} is not on sale.")
        if tt.sales_start and now < tt.sales_start:
            raise ValidationError(f"Sales for {tt.name} have not started yet.")
        if tt.sales_end and now > tt.sales_end:
            raise ValidationError(f"Sales for {tt.name} have ended.")
        # Safe to trust this count: the row is locked, so nobody can take tickets meanwhile
        if item["quantity"] > tt.available:
            raise SoldOut(f"Only {tt.available} {tt.name} ticket(s) left.")

    # Everything passed: write the order, its lines and its total
    order = Order.objects.create(buyer=buyer)
    total = Decimal("0.00")
    for item in items:
        tt = ticket_types[item["ticket_type"]]
        OrderItem.objects.create(
            order=order,
            ticket_type=tt,
            quantity=item["quantity"],
            unit_price=tt.price,  # copy today's price onto the line
        )
        total += tt.price * item["quantity"]

    order.total = total
    order.save(update_fields=["total", "updated_at"])
    return order