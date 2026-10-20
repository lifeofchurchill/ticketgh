from django.utils import timezone
from rest_framework import generics

from .models import Event
from .serializers import EventListSerializer


# GET /api/v1/events/ : public list of upcoming published events
class EventListView(generics.ListAPIView):
    serializer_class = EventListSerializer  # how each event is turned into JSON

    def get_queryset(self):
        # Runs on every request, so "now" is always the current time
        return Event.objects.filter(
            status=Event.Status.PUBLISHED,  # drafts and cancelled events stay hidden
            ends_at__gte=timezone.now(),    # hide events that have already ended
        )