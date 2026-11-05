from django.contrib import admin

from .models import Order, OrderItem


# Shows an order's lines as a table inside the order's page
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # no empty rows: items are created by the API, not by hand


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "buyer", "status", "total", "expires_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["reference", "buyer__email"]  # search by reference or buyer's email
    readonly_fields = ["reference", "created_at", "updated_at"]  # shown, never edited
    inlines = [OrderItemInline]