from django.urls import path

from . import views

urlpatterns = [
    # /api/v1/events/ -> list of upcoming published events
    path("events/", views.EventListView.as_view(), name="event-list"),
    path("events/<slug:slug>/", views.EventDetailView.as_view(), name="event-detail"),
]