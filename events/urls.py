from django.urls import path

from . import views

urlpatterns = [
    # GET: list of upcoming published events / POST: organizers create an event
    path("events/", views.EventListCreateView.as_view(), name="event-list"),
    # GET / PATCH / DELETE one event
    path("events/<slug:slug>/", views.EventDetailView.as_view(), name="event-detail"),
    # GET: an event's ticket types / POST: the owner adds one
    path("events/<slug:slug>/ticket-types/", views.TicketTypeListCreateView.as_view(), name="ticket-type-list"),
    # POST: the owner publishes their draft
    path("events/<slug:slug>/publish/", views.EventPublishView.as_view(), name="event-publish"),
]