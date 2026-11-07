from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order, OrderItem

# Every test in this file may use the (temporary) test database
pytestmark = pytest.mark.django_db


# ---------- Fixtures: events used by several tests ----------

def future_times():
    # A start time a month from now, and an end eight hours later
    start = timezone.now() + timedelta(days=30)
    return start, start + timedelta(hours=8)


@pytest.fixture
def draft_event(organizer):
    # A draft belonging to the "organizer" fixture from conftest.py
    start, end = future_times()
    return Event.objects.create(
        organizer=organizer,
        title="Draft Event",
        slug="draft-event",
        venue_name="Test Venue",
        city="Accra",
        starts_at=start,
        ends_at=end,
    )


@pytest.fixture
def published_event(other_organizer):
    # A published event belonging to a DIFFERENT organizer
    start, end = future_times()
    return Event.objects.create(
        organizer=other_organizer,
        title="Published Event",
        slug="published-event",
        venue_name="Test Venue",
        city="Kumasi",
        starts_at=start,
        ends_at=end,
        status=Event.Status.PUBLISHED,
    )


# ---------- Public browsing ----------

def test_public_list_shows_published_events_only(api_client, draft_event, published_event):
    # Act: a guest asks for the list
    response = api_client.get(reverse("event-list"))

    # Assert: only the published event is there
    assert response.status_code == 200
    slugs = [event["slug"] for event in response.data["results"]]
    assert slugs == ["published-event"]


def test_draft_detail_is_hidden_from_the_public(api_client, draft_event):
    response = api_client.get(reverse("event-detail", kwargs={"slug": draft_event.slug}))
    assert response.status_code == 404


# ---------- Creating events ----------

def test_attendee_cannot_create_event(api_client, attendee):
    # Arrange: log in as an attendee
    api_client.force_authenticate(user=attendee)
    start, end = future_times()
    data = {
        "title": "Not Allowed",
        "venue_name": "Venue",
        "city": "Accra",
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
    }

    # Act
    response = api_client.post(reverse("event-list"), data, format="json")

    # Assert: blocked, and nothing was saved
    assert response.status_code == 403
    assert Event.objects.count() == 0


def test_organizer_creates_draft_event(api_client, organizer):
    api_client.force_authenticate(user=organizer)
    start, end = future_times()
    data = {
        "title": "Accra Tech Summit",
        "venue_name": "AICC",
        "city": "Accra",
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "status": "published",  # should be ignored
    }

    response = api_client.post(reverse("event-list"), data, format="json")

    assert response.status_code == 201
    assert response.data["slug"] == "accra-tech-summit"
    assert response.data["status"] == "draft"             # status was read-only
    event = Event.objects.get(slug="accra-tech-summit")
    assert event.organizer == organizer                   # organizer came from the login


def test_event_must_end_after_it_starts(api_client, organizer):
    api_client.force_authenticate(user=organizer)
    start, end = future_times()
    data = {
        "title": "Backwards",
        "venue_name": "Venue",
        "city": "Accra",
        "starts_at": end.isoformat(),    # swapped on purpose
        "ends_at": start.isoformat(),
    }

    response = api_client.post(reverse("event-list"), data, format="json")

    assert response.status_code == 400
    assert "ends_at" in response.data


# ---------- Owners only ----------

def test_organizer_cannot_edit_someone_elses_event(api_client, organizer, published_event):
    api_client.force_authenticate(user=organizer)
    url = reverse("event-detail", kwargs={"slug": published_event.slug})

    response = api_client.patch(url, {"title": "Hijacked"}, format="json")

    assert response.status_code == 403
    published_event.refresh_from_db()  # reload from the database
    assert published_event.title == "Published Event"


def test_published_event_cannot_be_deleted(api_client, other_organizer, published_event):
    # The real owner tries to delete their published event
    api_client.force_authenticate(user=other_organizer)
    url = reverse("event-detail", kwargs={"slug": published_event.slug})

    response = api_client.delete(url)

    assert response.status_code == 400
    assert Event.objects.filter(pk=published_event.pk).exists()


# ---------- Publishing ----------

def test_cannot_publish_without_ticket_types(api_client, organizer, draft_event):
    api_client.force_authenticate(user=organizer)
    url = reverse("event-publish", kwargs={"slug": draft_event.slug})

    response = api_client.post(url)

    assert response.status_code == 400
    draft_event.refresh_from_db()
    assert draft_event.status == Event.Status.DRAFT


def test_owner_publishes_event_with_ticket_types(api_client, organizer, draft_event):
    # Arrange: give the draft a ticket type
    TicketType.objects.create(event=draft_event, name="Regular", price="100.00", quantity=100)
    api_client.force_authenticate(user=organizer)
    url = reverse("event-publish", kwargs={"slug": draft_event.slug})

    response = api_client.post(url)

    assert response.status_code == 200
    draft_event.refresh_from_db()
    assert draft_event.status == Event.Status.PUBLISHED

# ---------- Cancelling ----------

def make_order(buyer, ticket_type, status):
    # Helper: an order with one ticket line, in the given status
    order = Order.objects.create(buyer=buyer, status=status)
    OrderItem.objects.create(order=order, ticket_type=ticket_type, quantity=1, unit_price=ticket_type.price)
    return order


def test_owner_cancels_event_and_buyers_are_handled(api_client, other_organizer, attendee, published_event):
    # Arrange: one paid buyer and one buyer still paying
    vip = TicketType.objects.create(event=published_event, name="VIP", price="500.00", quantity=10)
    paid = make_order(attendee, vip, Order.Status.PAID)
    pending = make_order(attendee, vip, Order.Status.PENDING)
    api_client.force_authenticate(user=other_organizer)  # the real owner

    # Act
    response = api_client.post(reverse("event-cancel", kwargs={"slug": published_event.slug}))

    # Assert: the reply reports both counts...
    assert response.status_code == 200
    assert response.data["refunds_pending"] == 1
    assert response.data["holds_released"] == 1
    # ...and the database really changed
    published_event.refresh_from_db()
    paid.refresh_from_db()
    pending.refresh_from_db()
    assert published_event.status == Event.Status.CANCELLED
    assert paid.status == Order.Status.REFUND_PENDING
    assert pending.status == Order.Status.EXPIRED


def test_cancelled_event_cannot_be_published_again(api_client, organizer, draft_event):
    TicketType.objects.create(event=draft_event, name="Regular", price="100.00", quantity=100)
    api_client.force_authenticate(user=organizer)
    api_client.post(reverse("event-cancel", kwargs={"slug": draft_event.slug}))

    response = api_client.post(reverse("event-publish", kwargs={"slug": draft_event.slug}))

    assert response.status_code == 400
    draft_event.refresh_from_db()
    assert draft_event.status == Event.Status.CANCELLED


def test_no_tickets_can_be_reserved_after_cancelling(api_client, attendee, other_organizer, published_event):
    vip = TicketType.objects.create(event=published_event, name="VIP", price="500.00", quantity=10)
    api_client.force_authenticate(user=other_organizer)
    api_client.post(reverse("event-cancel", kwargs={"slug": published_event.slug}))

    # Switch the fake app to the buyer and try to reserve
    api_client.force_authenticate(user=attendee)
    response = api_client.post(
        reverse("order-list"),
        {"items": [{"ticket_type": vip.id, "quantity": 1}]},
        format="json",
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


def test_organizer_cannot_cancel_someone_elses_event(api_client, organizer, published_event):
    api_client.force_authenticate(user=organizer)  # not the owner

    response = api_client.post(reverse("event-cancel", kwargs={"slug": published_event.slug}))

    assert response.status_code == 404
    published_event.refresh_from_db()
    assert published_event.status == Event.Status.PUBLISHED


def test_cancelled_event_shows_its_status_but_leaves_the_list(api_client, published_event):
    published_event.status = Event.Status.CANCELLED
    published_event.save()

    detail = api_client.get(reverse("event-detail", kwargs={"slug": published_event.slug}))
    listing = api_client.get(reverse("event-list"))

    assert detail.status_code == 200
    assert detail.data["status"] == "cancelled"  # buyers can see what happened
    assert listing.data["count"] == 0            # but it's no longer advertised