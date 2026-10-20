"""Business rules for seat reservation. All state changes run inside a transaction."""
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from core.exceptions import Conflict

from .models import Booking, Seat

MAX_SEATS_PER_BOOKING = 10

ALLOWED_TRANSITIONS = {
    Booking.Status.PENDING.value: {
        Booking.Status.CONFIRMED.value,
        Booking.Status.CANCELLED.value,
    },
    Booking.Status.CONFIRMED.value: {Booking.Status.CANCELLED.value},
    Booking.Status.CANCELLED.value: set(),
}


@transaction.atomic
def create_booking(*, user, event, seat_ids):
    """Reserve seats atomically; row locks stop two users booking the same seat."""
    seats = list(
        Seat.objects.select_for_update().filter(event=event, id__in=seat_ids).order_by("id")
    )
    missing = sorted(set(seat_ids) - {seat.id for seat in seats})
    if missing:
        raise ValidationError({"seat_ids": [f"Seats not found for this event: {missing}."]})
    taken = [seat.id for seat in seats if seat.status != Seat.Status.AVAILABLE]
    if taken:
        raise Conflict(f"Seats are no longer available: {taken}.")

    Seat.objects.filter(id__in=[seat.id for seat in seats]).update(status=Seat.Status.BOOKED)
    total = sum((seat.price for seat in seats), Decimal("0.00"))
    booking = Booking.objects.create(user=user, event=event, total_amount=total)
    booking.seats.set(seats)
    return booking


def release_seats(booking):
    seat_ids = list(booking.seats.values_list("id", flat=True))
    Seat.objects.filter(id__in=seat_ids).update(status=Seat.Status.AVAILABLE)


@transaction.atomic
def change_booking_status(booking, new_status):
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if new_status == booking.status:
        return booking
    if new_status not in ALLOWED_TRANSITIONS[booking.status]:
        raise Conflict(f"Cannot change booking from '{booking.status}' to '{new_status}'.")
    if new_status == Booking.Status.CANCELLED:
        release_seats(booking)
    booking.status = new_status
    booking.save(update_fields=["status", "updated_at"])
    return booking
