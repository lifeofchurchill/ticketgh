from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "organizer", "city", "starts_at", "status"]
    list_filter = ["status", "category", "city"]
    search_fields = ["title", "venue_name", "city"]
    prepopulated_fields = {"slug": ["title"]}