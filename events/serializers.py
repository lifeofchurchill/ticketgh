from rest_framework import serializers

from .models import Event


# Translates Event objects into JSON for the public events list
class EventListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event  # which model to translate
        fields = [     # exactly which fields appear in the JSON
            "id",
            "title",
            "slug",
            "category",
            "venue_name",
            "city",
            "starts_at",
            "ends_at",
        ]