from django.db import models

# Create your models here.
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# How long tickets are held while the buyer pays (spec rule 9)
RESERVATION_MINUTES = 10

# Letters and digits that can't be confused when read aloud or typed (no 0/O, 1/I/L)
REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_reference():
    # A short, unguessable order code, e.g. "TGH-7KQ2M9XA"
    code = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(8))
    return f"TGH-{code}"


def reservation_deadline():
    # Runs at the moment each order is created: now + 10 minutes
    return timezone.now() + timedelta(minutes=RESERVATION_MINUTES)


# One purchase: who is buying, the total, and how long the tickets are held
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        PAID = "paid", "Paid"
        EXPIRED = "expired", "Expired"
        REFUND_PENDING = "refund_pending", "Refund pending"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # never lose a record of who paid
        related_name="orders",
    )
    reference = models.CharField(
        max_length=20,
        unique=True,
        default=generate_reference,  # filled in automatically
        editable=False,              # nobody types or changes it
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    expires_at = models.DateTimeField(default=reservation_deadline)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]  # newest orders first

    def __str__(self):
        return self.reference


# One line on an order: which ticket type, how many, at what price
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,  # lines mean nothing without their order
        related_name="items",
    )
    ticket_type = models.ForeignKey(
        "events.TicketType",
        on_delete=models.PROTECT,  # a ticket type with sales can't be deleted
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # price at purchase time

    def __str__(self):
        return f"{self.quantity} x {self.ticket_type.name}"

    @property
    def subtotal(self):
        # Price of this line: e.g. 2 x GHS 500.00 = GHS 1,000.00
        return self.unit_price * self.quantity