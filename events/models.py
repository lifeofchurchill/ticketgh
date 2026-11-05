from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q, Sum
from django.utils import timezone


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    class Category(models.TextChoices):
        MUSIC = "music", "Music"
        CONFERENCE = "conference", "Conference"
        RELIGIOUS = "religious", "Religious"
        SPORTS = "sports", "Sports"
        ARTS = "arts", "Arts and culture"
        OTHER = "other", "Other"

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.OTHER
    )
    venue_name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The event must end after it starts."})

class TicketType(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="ticket_types",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    quantity = models.PositiveIntegerField()
    sales_start = models.DateTimeField(null=True, blank=True)
    sales_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="unique_ticket_name_per_event",
            ),
        ]

    def __str__(self):
        return f"{self.event.title}: {self.name}"

    def clean(self):
        if self.sales_start and self.sales_end and self.sales_end <= self.sales_start:
            raise ValidationError({"sales_end": "Sales must end after they start."})

    def tickets_taken(self):
        # Tickets that are gone: paid for, or held by a pending order that hasn't expired
        from orders.models import Order  # imported here to avoid a circular import

        taken = self.order_items.filter(
            Q(order__status=Order.Status.PAID)
            | Q(order__status=Order.Status.PENDING, order__expires_at__gt=timezone.now())
        ).aggregate(total=Sum("quantity"))["total"]
        return taken or 0

    @property
    def available(self):
        # Tickets still on sale right now (never below zero)
        return max(self.quantity - self.tickets_taken(), 0)