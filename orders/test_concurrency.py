import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from events.models import Event, TicketType
from orders.models import Order
from orders.services import SoldOut, reserve_tickets
from users.models import User

# How many buyers race for the tickets
BUYERS = 10


# transaction=True: real commits, so every thread can see the data (see Step 2)
@pytest.mark.django_db(transaction=True)
def test_many_buyers_cannot_oversell_the_last_tickets(organizer):
    # ---------- Arrange: 3 VIP tickets, 10 buyers ----------
    start = timezone.now() + timedelta(days=30)
    event = Event.objects.create(
        organizer=organizer,
        title="Sold Out Show",
        slug="sold-out-show",
        venue_name="El Wak Stadium",
        city="Accra",
        starts_at=start,
        ends_at=start + timedelta(hours=5),
        status=Event.Status.PUBLISHED,
    )
    vip = TicketType.objects.create(event=event, name="VIP", price="500.00", quantity=3)
    buyers = [
        User.objects.create_user(email=f"buyer{i}@example.com", password="Test-pass-2026")
        for i in range(BUYERS)
    ]

    barrier = threading.Barrier(BUYERS, timeout=10)  # the starting line
    results = []  # "ok" or "sold_out", one per buyer
    errors = []   # anything unexpected

    # What each buyer's thread does
    def buy(buyer):
        try:
            barrier.wait()  # wait until all 10 are ready, then everyone goes at once
            reserve_tickets(buyer, [{"ticket_type": vip.id, "quantity": 1}])
            results.append("ok")
        except SoldOut:
            results.append("sold_out")
        except Exception as error:
            errors.append(error)
        finally:
            connection.close()  # each thread opened its own database connection

    # ---------- Act: start all 10 buyers, then wait for them all to finish ----------
    threads = [threading.Thread(target=buy, args=(buyer,)) for buyer in buyers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # ---------- Assert: exactly 3 winners, 7 polite refusals, no oversell ----------
    assert errors == []                       # nothing crashed
    assert results.count("ok") == 3           # exactly as many winners as tickets
    assert results.count("sold_out") == 7     # everyone else was told the truth
    assert Order.objects.count() == 3         # only 3 orders exist in the database
    assert vip.available == 0                 # sold out, not negative