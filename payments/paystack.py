from decimal import Decimal

import requests
from django.conf import settings

BASE_URL = "https://api.paystack.co"
TIMEOUT_SECONDS = 10  # never wait forever for another company's server


# Raised when Paystack can't be reached, or refuses the request
class PaystackError(Exception):
    pass


def to_pesewas(amount):
    # Decimal("500.00") -> 50000; Paystack wants whole pesewas, never decimals
    return int((amount * 100).quantize(Decimal("1")))


def _headers():
    # Our secret key identifies TicketGH to Paystack
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}


def initialize_transaction(email, amount, reference):
    # Ask Paystack to create a payment page; returns its data (including authorization_url)
    data = {
        "email": email,
        "amount": to_pesewas(amount),
        "currency": "GHS",
        "reference": reference,
    }
    try:
        response = requests.post(
            f"{BASE_URL}/transaction/initialize",
            json=data,
            headers=_headers(),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        # No internet, Paystack down, or too slow: we never got an answer
        raise PaystackError("Could not reach Paystack.") from error

    try:
        body = response.json()
    except ValueError:
        body = {}  # the reply wasn't JSON (for example, an error page)

    if response.status_code != 200 or not body.get("status"):
        raise PaystackError(body.get("message", "Paystack refused the request."))
    return body["data"]