from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from ticketing.models import Booking, Seat, Tag, Venue

pytestmark = pytest.mark.django_db


def test_venue_str_and_capacity_validation(venue):
    assert str(venue) == "Grand Hall (Johannesburg)"
    venue.capacity = 0
    with pytest.raises(ValidationError):
        venue.full_clean()


def test_venue_name_city_is_unique(venue):
    with pytest.raises(IntegrityError), transaction.atomic():
        Venue.objects.create(name=venue.name, city=venue.city, capacity=10)


def test_event_tags_many_to_many(event):
    tag = Tag.objects.create(name="jazz")
    event.tags.add(tag)
    assert str(tag) == "jazz"
    assert str(event) == "Jazz Night"
    assert list(tag.events.all()) == [event]


def test_event_price_validation(event):
    event.base_price = Decimal("-1.00")
    with pytest.raises(ValidationError):
        event.full_clean()


def test_seat_str_and_uniqueness(event, seats):
    assert str(seats[0]) == "A-A1"
    with pytest.raises(IntegrityError), transaction.atomic():
        Seat.objects.create(event=event, section="A", row="A", number=1, price=Decimal("1"))


def test_booking_links_user_event_and_seats(member, event, seats):
    booking = Booking.objects.create(user=member, event=event, total_amount=Decimal("300"))
    booking.seats.set(seats[:2])
    assert booking.status == Booking.Status.PENDING
    assert booking.seats.count() == 2
    assert str(booking).startswith("Booking ")
    assert list(member.bookings.all()) == [booking]
