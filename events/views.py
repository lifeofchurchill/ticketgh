from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions
from rest_framework.exceptions import ValidationError

from .filters import EventFilter
from .models import Event
from .permissions import IsEventOwner, IsOrganizer
from .serializers import EventDetailSerializer, EventListSerializer, EventWriteSerializer


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
        # Everyone can find published events
        visible = Q(status=Event.Status.PUBLISHED)
        # Logged-in users can also find their own events, including drafts
        if self.request.user.is_authenticated:
            visible = visible | Q(organizer=self.request.user)
        return Event.objects.filter(visible)

    def perform_destroy(self, instance):
        # Spec: only drafts can be deleted; published events must be cancelled instead
        if instance.status != Event.Status.DRAFT:
            raise ValidationError("Only draft events can be deleted.")
        instance.delete()