from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions
from .filters import EventFilter
from .models import Event
from .permissions import IsOrganizer
from .serializers import EventCreateSerializer, EventDetailSerializer, EventListSerializer


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
            return EventCreateSerializer    # checks incoming event data
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


# GET /api/v1/events/<slug>/ : full details of one published event
class EventDetailView(generics.RetrieveAPIView):
    serializer_class = EventDetailSerializer  # full version, with ticket types
    permission_classes = [permissions.AllowAny]  # public: guests can browse events
    lookup_field = "slug"                     # find the event by its slug, not its ID

    def get_queryset(self):
        # Only published events can be viewed; drafts return 404 Not Found
        return Event.objects.filter(status=Event.Status.PUBLISHED)