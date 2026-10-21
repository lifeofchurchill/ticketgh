from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics

from .filters import EventFilter
from .models import Event
from .serializers import EventDetailSerializer, EventListSerializer


# GET /api/v1/events/ : public list of upcoming published events
class EventListView(generics.ListAPIView):
    serializer_class = EventListSerializer  # how each event is turned into JSON

    # The tools that can narrow down or reorder the list
    filter_backends = [
        DjangoFilterBackend,     # ?city=accra&category=music
        filters.SearchFilter,    # ?search=afro
        filters.OrderingFilter,  # ?ordering=-starts_at
    ]
    filterset_class = EventFilter                # which filters are allowed
    search_fields = ["title", "venue_name"]      # where ?search= looks
    ordering_fields = ["starts_at", "title"]     # what ?ordering= may sort by

    def get_queryset(self):
        # Runs on every request, so "now" is always the current time
        return Event.objects.filter(
            status=Event.Status.PUBLISHED,  # drafts and cancelled events stay hidden
            ends_at__gte=timezone.now(),    # hide events that have already ended
        )


# GET /api/v1/events/<slug>/ : full details of one published event
class EventDetailView(generics.RetrieveAPIView):
    serializer_class = EventDetailSerializer  # full version, with ticket types
    lookup_field = "slug"                     # find the event by its slug, not its ID

    def get_queryset(self):
        # Only published events can be viewed; drafts return 404 Not Found
        return Event.objects.filter(status=Event.Status.PUBLISHED)