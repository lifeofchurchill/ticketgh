from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    class Category(models.TextChoices):
        MUSIC = "music", "Music"
        CONFERENCE = "conference", "Conference"
        RELIGIOUS = "religious", "Religious"
        SPORTS = "sports", "Sports"
        ARTS = "arts", "Arts and culture"
        OTHER = "other", "Other"

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.OTHER
    )
    venue_name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The event must end after it starts."})