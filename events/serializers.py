from rest_framework import serializers
from django.utils import timezone
from django.utils.text import slugify
from .models import Event, TicketType


# Translates a TicketType into JSON (used inside the event detail)
class TicketTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        fields = ["id", "name", "description", "price", "sales_start", "sales_end"]

    # Checks the data an owner sends to add a ticket type to their event
class TicketTypeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketType
        # Owners send quantity too; the public version hides it
        fields = ["id", "name", "description", "price", "quantity", "sales_start", "sales_end"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        # The view passes the event in; one event can't have two tickets with the same name
        event = self.context["event"]
        if TicketType.objects.filter(event=event, name__iexact=value).exists():
            raise serializers.ValidationError("This event already has a ticket type with this name.")
        return value

    def validate(self, attrs):
        # Same rule as TicketType.clean(): DRF doesn't call the model's clean()
        sales_start = attrs.get("sales_start")
        sales_end = attrs.get("sales_end")
        if sales_start and sales_end and sales_end <= sales_start:
            raise serializers.ValidationError({"sales_end": "Sales must end after they start."})
        return attrs


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

# Builds a slug from the title, adding -2, -3... if it's already taken
def make_unique_slug(title):
    base = slugify(title) or "event"  # "Afrochella 2026" -> "afrochella-2026"
    slug = base
    counter = 2
    while Event.objects.filter(slug=slug).exists():
        slug = f"{base}-{counter}"  # afrochella-2026-2, afrochella-2026-3...
        counter += 1
    return slug


# Checks the data an organizer sends to create (POST) or edit (PATCH) an event
class EventWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "venue_name",
            "city",
            "address",
            "starts_at",
            "ends_at",
            "status",
        ]
        # Shown in the response, but the organizer can't set them
        read_only_fields = ["id", "slug", "status"]

    def validate(self, attrs):
        # self.instance is None when creating, or the existing event when editing.
        # On edits, a field that wasn't sent keeps its current value.
        instance = self.instance
        starts_at = attrs.get("starts_at", instance.starts_at if instance else None)
        ends_at = attrs.get("ends_at", instance.ends_at if instance else None)

        # Only insist on a future start when a start time is being set
        if "starts_at" in attrs and starts_at <= timezone.now():
            raise serializers.ValidationError({"starts_at": "The event must start in the future."})
        if ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "The event must end after it starts."})
        return attrs

    def create(self, validated_data):
        # Generate the slug ourselves, then let DRF save the event as usual
        validated_data["slug"] = make_unique_slug(validated_data["title"])
        return super().create(validated_data)