from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .services import cancel_event

from .filters import EventFilter
from .models import Event, TicketType
from .permissions import IsEventOwner, IsOrganizer
from .serializers import (
    EventDetailSerializer,
    EventListSerializer,
    EventWriteSerializer,
    TicketTypeSerializer,
    TicketTypeWriteSerializer,
)


# Events this user may see: published and cancelled ones, plus their own (including drafts)
def visible_events(user):
    visible = Q(status__in=[Event.Status.PUBLISHED, Event.Status.CANCELLED])
    if user.is_authenticated:
        visible = visible | Q(organizer=user)
    return Event.objects.filter(visible)


# GET  /api/v1/events/ : public list of upcoming published events
# POST /api/v1/events/ : organizers create a new draft event
class EventListCreateView(generics.ListCreateAPIView):
    # The tools that can narrow down or reorder the list (GET only)
    filter_backends = [
        DjangoFilterBackend,     # ?city=accra&category=music
        filters.SearchFilter,    # ?search=afro
        filters.OrderingFilter,  # ?ordering=-starts_at
    ]
    filterset_class = EventFilter                # which filters are allowed
    search_fields = ["title", "venue_name"]      # where ?search= looks
    ordering_fields = ["starts_at", "title"]     # what ?ordering= may sort by

    def get_permissions(self):
        # Different rules for different methods
        if self.request.method == "POST":
            return [IsOrganizer()]          # creating: organizers only
        return [permissions.AllowAny()]     # listing: anyone

    def get_serializer_class(self):
        # Different translators for different methods
        if self.request.method == "POST":
            return EventWriteSerializer     # checks incoming event data
        return EventListSerializer          # short version for event cards

    def get_queryset(self):
        # Runs on every request, so "now" is always the current time
        return Event.objects.filter(
            status=Event.Status.PUBLISHED,  # drafts and cancelled events stay hidden
            ends_at__gte=timezone.now(),    # hide events that have already ended
        )

    def perform_create(self, serializer):
        # The organizer is whoever is logged in; it can't be chosen in the request
        serializer.save(organizer=self.request.user)


# GET    /api/v1/events/<slug>/ : anyone views a published event (owners also see drafts)
# PATCH  /api/v1/events/<slug>/ : the owner edits their event
# DELETE /api/v1/events/<slug>/ : the owner deletes their draft
class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    lookup_field = "slug"                                     # find events by slug
    http_method_names = ["get", "patch", "delete", "head", "options"]  # no PUT

    def get_permissions(self):
        # Reading is open; changing needs an organizer who owns this event
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsOrganizer(), IsEventOwner()]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return EventWriteSerializer     # same rules as creating
        return EventDetailSerializer        # full details with ticket types

    def get_queryset(self):
        # Published events, plus the user's own drafts
        return visible_events(self.request.user)

    def perform_destroy(self, instance):
        # Spec: only drafts can be deleted; published events must be cancelled instead
        if instance.status != Event.Status.DRAFT:
            raise ValidationError("Only draft events can be deleted.")
        instance.delete()


# GET  /api/v1/events/<slug>/ticket-types/ : anyone lists an event's ticket types
# POST /api/v1/events/<slug>/ticket-types/ : the owner adds a ticket type
class TicketTypeListCreateView(generics.ListCreateAPIView):

    def get_permissions(self):
        # Reading is open; adding needs an organizer who owns the event
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [IsOrganizer(), IsEventOwner()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketTypeWriteSerializer  # owner's version, with quantity
        return TicketTypeSerializer           # public version

    def get_event(self):
        # Find the event named in the address, once per request
        if not hasattr(self, "_event"):
            event = get_object_or_404(visible_events(self.request.user), slug=self.kwargs["slug"])
            # Run IsEventOwner against this event (it only applies to POST)
            self.check_object_permissions(self.request, event)
            self._event = event
        return self._event

    def get_queryset(self):
        # Only this event's ticket types
        return TicketType.objects.filter(event=self.get_event())

    def get_serializer_context(self):
        # Hand the event to the serializer so validate_name() can use it
        context = super().get_serializer_context()
        if self.request.method == "POST":
            context["event"] = self.get_event()
        return context

    def perform_create(self, serializer):
        # The event comes from the address, not from the request body
        serializer.save(event=self.get_event())


# POST /api/v1/events/<slug>/publish/ : the owner publishes their draft
class EventPublishView(generics.GenericAPIView):
    lookup_field = "slug"
    permission_classes = [IsOrganizer, IsEventOwner]  # same rules for every method
    serializer_class = EventDetailSerializer          # used for the reply

    def get_queryset(self):
        # Organizers can only ever publish their own events
        return Event.objects.filter(organizer=self.request.user)

    def post(self, request, *args, **kwargs):
        event = self.get_object()  # finds the event and runs IsEventOwner

        # Spec rule 3: check everything before publishing
        if event.status != Event.Status.DRAFT:
            raise ValidationError("Only draft events can be published.")
        if not event.ticket_types.exists():
            raise ValidationError("Add at least one ticket type before publishing.")
        if event.starts_at <= timezone.now():
            raise ValidationError("This event has already started.")

        # All checks passed: publish
        event.status = Event.Status.PUBLISHED
        event.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(event).data)

# POST /api/v1/events/<slug>/cancel/ : the owner cancels their event
class EventCancelView(generics.GenericAPIView):
    lookup_field = "slug"
    permission_classes = [IsOrganizer, IsEventOwner]  # same rules as publishing
    serializer_class = EventDetailSerializer          # used for the reply

    def get_queryset(self):
        # Organizers can only ever cancel their own events
        return Event.objects.filter(organizer=self.request.user)

    def post(self, request, *args, **kwargs):
        event = self.get_object()      # finds the event and runs IsEventOwner
        result = cancel_event(event)   # the rules and every change, in one transaction
        return Response({
            "event": self.get_serializer(result["event"]).data,
            "refunds_pending": result["refunds_pending"],  # paid buyers to refund
            "holds_released": result["holds_released"],    # pending orders stopped
        })