from django.db import models


# One attempt to pay for an order through Paystack
class Payment(models.Model):
    class Status(models.TextChoices):
        INITIALIZED = "initialized", "Initialized"  # payment page created, not paid yet
        SUCCESS = "success", "Success"              # Paystack confirmed the money arrived
        FAILED = "failed", "Failed"                 # Paystack says it didn't go through

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,  # never lose a record of money
        related_name="payments",
    )
    provider = models.CharField(max_length=20, default="paystack")
    reference = models.CharField(max_length=40, unique=True)  # our ID for this attempt, sent to Paystack
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # in GHS, copied from the order
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.INITIALIZED
    )
    authorization_url = models.URLField(blank=True)  # the payment page Paystack gave us
    provider_response = models.JSONField(default=dict, blank=True)  # Paystack's raw reply, for audits
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} ({self.status})"