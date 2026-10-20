from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from ticketing.models import Event, Seat, Tag, Venue
from tests.helpers import assert_error

pytestmark = pytest.mark.django_db


def future(days=3):
    return (timezone.now() + timedelta(days=days)).isoformat()


def event_payload(venue, **overrides):
    payload = {"venue": venue.id, "title": "Rock Fest", "description": "Loud",
               "starts_at": future(), "base_price": "99.00"}
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- venues
def test_admin_full_crud_on_venues(admin_client):
    created = admin_client.post(
        "/api/venues/", {"name": "Arena", "city": "Cape Town", "capacity": 500}
    )
    assert created.status_code == 201
    url = f"/api/venues/{created.json()['id']}/"
    assert admin_client.get(url).status_code == 200
    patched = admin_client.patch(url, {"capacity": 600})
    assert patched.status_code == 200 and patched.json()["capacity"] == 600
    assert admin_client.delete(url).status_code == 204
    assert_error(admin_client.get(url), 404, "not_found")


def test_member_can_read_but_not_write_venues(member_client, venue):
    assert member_client.get("/api/venues/").status_code == 200
    response = member_client.post(
        "/api/venues/", {"name": "X", "city": "Y", "capacity": 5}
    )
    assert_error(response, 403, "permission_denied")


def test_venues_require_authentication(anon):
    assert_error(anon.get("/api/venues/"), 401, "unauthorized")


def test_venue_validation_errors_use_schema(admin_client):
    response = admin_client.post("/api/venues/", {"name": "X", "city": "Y", "capacity": 0})
    error = assert_error(response, 400, "validation_error")
    assert "capacity" in error["details"]


def test_venue_search(admin_client, venue):
    Venue.objects.create(name="Arena", city="Cape Town", capacity=10)
    assert admin_client.get("/api/venues/", {"search": "Cape"}).json()["count"] == 1


def test_cannot_delete_venue_that_has_events(admin_client, event):
    response = admin_client.delete(f"/api/venues/{event.venue_id}/")
    assert_error(response, 409, "conflict")


# ------------------------------------------------------------------ tags
def test_tag_crud_and_permissions(admin_client, member_client):
    created = admin_client.post("/api/tags/", {"name": "jazz"})
    assert created.status_code == 201
    assert_error(admin_client.post("/api/tags/", {"name": "jazz"}), 400, "validation_error")
    assert member_client.get("/api/tags/").json()["count"] == 1
    assert_error(member_client.post("/api/tags/", {"name": "x"}), 403, "permission_denied")
    assert admin_client.delete(f"/api/tags/{created.json()['id']}/").status_code == 204


# ---------------------------------------------------------------- events
def test_admin_creates_event_with_tags(admin_client, admin, venue):
    tag = Tag.objects.create(name="rock")
    response = admin_client.post("/api/events/", event_payload(venue, tags=[tag.id]))
    assert response.status_code == 201
    body = response.json()
    assert body["tags"] == [tag.id]
    assert body["created_by"] == admin.id
    assert body["status"] == "published"
    assert body["seats_available"] == 0


def test_member_cannot_create_event(member_client, venue):
    response = member_client.post("/api/events/", event_payload(venue))
    assert_error(response, 403, "permission_denied")


def test_event_start_must_be_in_future_on_create(admin_client, venue):
    past = (timezone.now() - timedelta(days=1)).isoformat()
    response = admin_client.post("/api/events/", event_payload(venue, starts_at=past))
    error = assert_error(response, 400, "validation_error")
    assert "starts_at" in error["details"]


def test_event_negative_price_rejected(admin_client, venue):
    response = admin_client.post("/api/events/", event_payload(venue, base_price="-5"))
    error = assert_error(response, 400, "validation_error")
    assert "base_price" in error["details"]


def test_event_list_reports_available_seats(member_client, event, seats):
    result = member_client.get("/api/events/").json()["results"][0]
    assert result["seats_available"] == 5
    assert member_client.get(f"/api/events/{event.id}/").json()["seats_available"] == 5


def test_drafts_hidden_from_members_but_visible_to_admins(
    admin_client, member_client, venue
):
    draft = Event.objects.create(
        venue=venue, title="Draft", starts_at=timezone.now() + timedelta(days=5),
        base_price=Decimal("10"), status=Event.Status.DRAFT,
    )
    assert member_client.get("/api/events/").json()["count"] == 0
    assert_error(member_client.get(f"/api/events/{draft.id}/"), 404, "not_found")
    assert admin_client.get(f"/api/events/{draft.id}/").status_code == 200


def test_event_filters_and_search(admin_client, venue, event):
    tag = Tag.objects.create(name="live")
    event.tags.add(tag)
    Event.objects.create(
        venue=venue, title="Draft Show", starts_at=timezone.now() + timedelta(days=30),
        base_price=Decimal("10"), status=Event.Status.DRAFT,
    )
    later = (timezone.now() + timedelta(days=20)).isoformat()

    def count(**params):
        return admin_client.get("/api/events/", params).json()["count"]

    assert count() == 2
    assert count(status="draft") == 1
    assert count(starts_after=later) == 1
    assert count(starts_before=later) == 1
    assert count(venue=venue.id) == 2
    assert count(tags=tag.id) == 1
    assert count(search="Jazz") == 1
    assert count(ordering="-starts_at") == 2


def test_event_filter_with_invalid_value_is_a_400(admin_client):
    assert_error(admin_client.get("/api/events/", {"venue": "abc"}), 400, "validation_error")


def test_admin_updates_event(admin_client, event):
    url = f"/api/events/{event.id}/"
    response = admin_client.patch(url, {"title": "Jazz Night II"})
    assert response.status_code == 200 and response.json()["title"] == "Jazz Night II"
    past = (timezone.now() - timedelta(days=1)).isoformat()
    assert admin_client.patch(url, {"starts_at": past}).status_code == 200


def test_admin_deletes_event_without_bookings(admin_client, event):
    assert admin_client.delete(f"/api/events/{event.id}/").status_code == 204


def test_cannot_delete_event_with_bookings(admin_client, member, event, seats):
    from ticketing.models import Booking

    Booking.objects.create(user=member, event=event)
    assert_error(admin_client.delete(f"/api/events/{event.id}/"), 409, "conflict")


# ------------------------------------------------------- seat generation
def generate(client, event, **payload):
    return client.post(f"/api/events/{event.id}/generate-seats/", payload)


def test_generate_seats_uses_event_price_by_default(admin_client, event):
    response = generate(admin_client, event, section="B", rows=2, seats_per_row=3)
    assert response.status_code == 201
    assert response.json() == {"created": 6, "section": "B"}
    assert event.seats.count() == 6
    assert event.seats.filter(row="B", number=3, price=Decimal("150.00")).exists()


def test_generate_seats_with_explicit_price(admin_client, event):
    generate(admin_client, event, section="C", rows=1, seats_per_row=2, price="75.50")
    assert event.seats.filter(section="C", price=Decimal("75.50")).count() == 2


def test_generate_seats_duplicate_section_conflicts(admin_client, event):
    generate(admin_client, event, section="B", rows=1, seats_per_row=1)
    response = generate(admin_client, event, section="B", rows=1, seats_per_row=1)
    assert_error(response, 409, "conflict")


def test_generate_seats_cannot_exceed_capacity(admin_client, event):
    response = generate(admin_client, event, section="Z", rows=10, seats_per_row=11)
    assert_error(response, 400, "validation_error")


def test_generate_seats_validates_input(admin_client, event):
    response = generate(admin_client, event, section="B", rows=0, seats_per_row=3)
    assert_error(response, 400, "validation_error")


def test_generate_seats_is_admin_only_and_404s_for_unknown_event(
    admin_client, member_client, event
):
    response = generate(member_client, event, section="B", rows=1, seats_per_row=1)
    assert_error(response, 403, "permission_denied")
    response = admin_client.post("/api/events/99999/generate-seats/",
                                 {"section": "B", "rows": 1, "seats_per_row": 1})
    assert_error(response, 404, "not_found")


# ----------------------------------------------------------------- seats
def test_admin_seat_crud(admin_client, event):
    payload = {"event": event.id, "section": "V", "row": "A", "number": 1, "price": "200.00"}
    created = admin_client.post("/api/seats/", payload)
    assert created.status_code == 201
    url = f"/api/seats/{created.json()['id']}/"
    patched = admin_client.patch(url, {"status": "booked"})
    assert patched.status_code == 200 and patched.json()["status"] == "booked"
    assert admin_client.delete(url).status_code == 204


def test_duplicate_seat_is_rejected(admin_client, event, seats):
    payload = {"event": event.id, "section": "A", "row": "A", "number": 1, "price": "1.00"}
    assert admin_client.post("/api/seats/", payload).status_code in (400, 409)


def test_seat_creation_respects_venue_capacity(admin_client, admin):
    small = Venue.objects.create(name="Tiny", city="Pretoria", capacity=1)
    tiny_event = Event.objects.create(
        venue=small, title="Tiny Show", starts_at=timezone.now() + timedelta(days=2),
        base_price=Decimal("5"), created_by=admin,
    )
    payload = {"event": tiny_event.id, "section": "A", "row": "A", "number": 1, "price": "5"}
    assert admin_client.post("/api/seats/", payload).status_code == 201
    payload["number"] = 2
    assert_error(admin_client.post("/api/seats/", payload), 400, "validation_error")


def test_members_can_filter_seats_but_not_modify(member_client, event, seats):
    Seat.objects.filter(id=seats[0].id).update(status=Seat.Status.BOOKED)
    listing = member_client.get("/api/seats/", {"event": event.id, "status": "available"})
    assert listing.json()["count"] == 4
    assert_error(member_client.delete(f"/api/seats/{seats[1].id}/"), 403, "permission_denied")
