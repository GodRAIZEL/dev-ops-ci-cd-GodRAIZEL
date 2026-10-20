from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from tests.helpers import PASSWORD
from ticketing.models import Event, Seat, Venue


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def admin(db):
    return User.objects.create_user(
        "admin", "admin@example.com", PASSWORD, role=User.Role.ADMIN
    )


@pytest.fixture
def member(db):
    return User.objects.create_user("member", "member@example.com", PASSWORD)


@pytest.fixture
def other_member(db):
    return User.objects.create_user("other", "other@example.com", PASSWORD)


@pytest.fixture
def admin_client(admin):
    return client_for(admin)


@pytest.fixture
def member_client(member):
    return client_for(member)


@pytest.fixture
def other_client(other_member):
    return client_for(other_member)


@pytest.fixture
def venue(db):
    return Venue.objects.create(name="Grand Hall", city="Johannesburg", capacity=100)


@pytest.fixture
def event(venue, admin):
    return Event.objects.create(
        venue=venue,
        title="Jazz Night",
        description="Live jazz",
        starts_at=timezone.now() + timedelta(days=7),
        base_price=Decimal("150.00"),
        created_by=admin,
    )


@pytest.fixture
def seats(event):
    Seat.objects.bulk_create(
        Seat(event=event, section="A", row="A", number=n, price=Decimal("150.00"))
        for n in range(1, 6)
    )
    return list(Seat.objects.filter(event=event).order_by("number"))
