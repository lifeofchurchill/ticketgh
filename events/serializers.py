from rest_framework import serializers

from .models import Event, TicketType


# Translates a TicketType into JSON (used inside the event detail)
class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "name", "description", "price", "sales_start", "sales_end"]


# Short version of an event, for the list of event cards
class EventListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "category",
            "venue_name",
            "city",
            "starts_at",
            "ends_at",
        ]


# Full version of an event: everything in the list version, plus more
class EventDetailSerializer(EventListSerializer):
    # Nest each ticket type's JSON inside the event's JSON
    ticket_types = TicketTypeSerializer(many=True, read_only=True)

    class Meta(EventListSerializer.Meta):
        # Reuse the list fields and add the extra detail fields
        fields = EventListSerializer.Meta.fields + [
            "description",
            "address",
            "ticket_types",
        ]