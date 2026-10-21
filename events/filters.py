import django_filters

from .models import Event


# Defines which query-string filters the events list accepts
class EventFilter(django_filters.FilterSet):
    # ?city=accra : matches "Accra", "ACCRA", "accra" (case doesn't matter)
    city = django_filters.CharFilter(lookup_expr="iexact")

    # ?starts_after=2026-12-01 : events starting on or after this date
    starts_after = django_filters.DateFilter(
        field_name="starts_at", lookup_expr="date__gte"
    )

    # ?starts_before=2026-12-31 : events starting on or before this date
    starts_before = django_filters.DateFilter(
        field_name="starts_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Event
        # ?category=music : exact match on these fields
        fields = ["category", "city"]