from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from orders.models import Order, OrderItem

from .models import Event, TicketType


@transaction.atomic  # the event and every affected order change together, or not at all
def cancel_event(event):
    # Rule: only drafts and published events can be cancelled (never twice, never a finished one)
    if event.status not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
        raise ValidationError("Only draft or published events can be cancelled.")
    if event.ends_at <= timezone.now():
        raise ValidationError("This event has already ended.")

    # Lock this event's ticket types: any purchase in progress finishes first,
    # so its order is caught by the updates below instead of slipping through
    list(TicketType.objects.select_for_update().filter(event=event))

    # 1. Cancel the event
    event.status = Event.Status.CANCELLED
    event.save(update_fields=["status", "updated_at"])

    # Every order with at least one line for this event
    order_ids = OrderItem.objects.filter(ticket_type__event=event).values("order_id")
    affected = Order.objects.filter(id__in=order_ids)
    now = timezone.now()

    # 2. Paid orders: the buyer must get their money back
    refunds_pending = affected.filter(status=Order.Status.PAID).update(
        status=Order.Status.REFUND_PENDING, updated_at=now
    )

    # 3. Pending orders: stop them, and release their held tickets
    holds_released = affected.filter(status=Order.Status.PENDING).update(
        status=Order.Status.EXPIRED, updated_at=now
    )

    return {
        "event": event,
        "refunds_pending": refunds_pending,
        "holds_released": holds_released,
    }