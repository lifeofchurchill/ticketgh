from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "order", "amount", "status", "created_at"]
    list_filter = ["status", "provider"]
    search_fields = ["reference", "order__reference", "order__buyer__email"]
    # Records of money are read-only in the admin
    readonly_fields = [
        "order", "provider", "reference", "amount", "status",
        "authorization_url", "provider_response", "created_at", "updated_at",
    ]