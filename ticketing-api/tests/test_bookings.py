from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from ticketing.models import Booking, Event, Seat
from tests.helpers import assert_error

pytestmark = pytest.mark.django_db

URL = "/api/bookings/"


def book(client, event, *seat_ids):
    return client.post(URL, {"event": event.id, "seat_ids": list(seat_ids)})


def booked_count():
    return Seat.objects.filter(status=Seat.Status.BOOKED).count()


def test_member_books_seats(member_client, member, event, seats):
    response = book(member_client, event, seats[0].id, seats[1].id)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_amount"] == "300.00"
    assert body["user"] == member.id
    assert len(body["seats"]) == 2
    assert all(seat["status"] == "booked" for seat in body["seats"])
    assert booked_count() == 2


def test_cannot_book_taken_seat(member_client, other_client, event, seats):
    assert book(member_client, event, seats[0].id).status_code == 201
    response = book(other_client, event, seats[0].id, seats[1].id)
    assert_error(response, 409, "conflict")
    assert booked_count() == 1  # failed attempt rolled back, seat 2 untouched


def test_seats_must_belong_to_the_event(member_client, event, seats, venue):
    other_event = Event.objects.create(
        venue=venue, title="Other", starts_at=timezone.now() + timedelta(days=9),
        base_price=Decimal("10"),
    )
    foreign = Seat.objects.create(event=other_event, section="Z", row="A", number=1,
                                  price=Decimal("10"))
    error = assert_error(book(member_client, event, foreign.id), 400, "validation_error")
    assert "seat_ids" in error["details"]
    assert_error(book(member_client, event, 999999), 400, "validation_error")


@pytest.mark.parametrize("seat_ids", [[], [1, 1], list(range(1, 12))])
def test_seat_id_list_is_validated(member_client, event, seats, seat_ids):
    response = member_client.post(URL, {"event": event.id, "seat_ids": seat_ids})
    error = assert_error(response, 400, "validation_error")
    assert "seat_ids" in error["details"]


def test_cannot_book_unpublished_or_started_events(member_client, event, seats):
    Event.objects.filter(pk=event.pk).update(status=Event.Status.DRAFT)
    assert_error(book(member_client, event, seats[0].id), 400, "validation_error")

    Event.objects.filter(pk=event.pk).update(
        status=Event.Status.PUBLISHED, starts_at=timezone.now() - timedelta(hours=1)
    )
    assert_error(book(member_client, event, seats[0].id), 400, "validation_error")


def test_bookings_require_authentication(anon):
    assert_error(anon.get(URL), 401, "unauthorized")


def test_members_only_see_their_own_bookings(
    member_client, other_client, admin_client, event, seats
):
    mine = book(member_client, event, seats[0].id).json()
    book(other_client, event, seats[1].id)

    assert member_client.get(URL).json()["count"] == 1
    assert admin_client.get(URL).json()["count"] == 2
    assert member_client.get(f"{URL}{mine['id']}/").status_code == 200
    other_booking = Booking.objects.exclude(pk=mine["id"]).get()
    assert_error(member_client.get(f"{URL}{other_booking.id}/"), 404, "not_found")
    assert member_client.get(URL, {"status": "cancelled"}).json()["count"] == 0
    assert member_client.get(URL, {"status": "pending"}).json()["count"] == 1


def test_owner_cancels_booking_and_seats_are_released(
    member_client, other_client, event, seats
):
    booking = book(member_client, event, seats[0].id, seats[1].id).json()
    assert_error(other_client.post(f"{URL}{booking['id']}/cancel/"), 404, "not_found")

    response = member_client.post(f"{URL}{booking['id']}/cancel/")
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert booked_count() == 0
    assert member_client.post(f"{URL}{booking['id']}/cancel/").status_code == 200  # idempotent
    assert book(other_client, event, seats[0].id).status_code == 201  # seat can be re-booked


def test_admin_confirms_then_cancels(admin_client, member_client, event, seats):
    booking = book(member_client, event, seats[0].id).json()
    url = f"{URL}{booking['id']}/"

    confirmed = admin_client.patch(url, {"status": "confirmed"})
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert len(confirmed.json()["seats"]) == 1
    assert admin_client.patch(url, {"status": "confirmed"}).status_code == 200  # no-op

    assert admin_client.put(url, {"status": "cancelled"}).status_code == 200
    assert booked_count() == 0
    assert_error(admin_client.patch(url, {"status": "confirmed"}), 409, "conflict")


def test_invalid_status_value_rejected(admin_client, member_client, event, seats):
    booking = book(member_client, event, seats[0].id).json()
    response = admin_client.patch(f"{URL}{booking['id']}/", {"status": "bogus"})
    assert_error(response, 400, "validation_error")


def test_members_cannot_edit_or_delete_bookings(member_client, event, seats):
    booking = book(member_client, event, seats[0].id).json()
    url = f"{URL}{booking['id']}/"
    assert_error(member_client.patch(url, {"status": "confirmed"}), 403, "permission_denied")
    assert_error(member_client.delete(url), 403, "permission_denied")


def test_admin_delete_releases_seats_of_active_booking(
    admin_client, member_client, event, seats
):
    booking = book(member_client, event, seats[0].id).json()
    assert admin_client.delete(f"{URL}{booking['id']}/").status_code == 204
    assert booked_count() == 0
    assert Booking.objects.count() == 0


def test_admin_delete_of_cancelled_booking_leaves_rebooked_seat_alone(
    admin_client, member_client, other_client, event, seats
):
    first = book(member_client, event, seats[0].id).json()
    member_client.post(f"{URL}{first['id']}/cancel/")
    book(other_client, event, seats[0].id)

    assert admin_client.delete(f"{URL}{first['id']}/").status_code == 204
    assert booked_count() == 1  # the second booking's seat is still booked
