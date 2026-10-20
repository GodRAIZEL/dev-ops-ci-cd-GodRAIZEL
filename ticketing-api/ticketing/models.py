import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

NON_NEGATIVE = [MinValueValidator(Decimal("0.00"))]


class Venue(models.Model):
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=80, db_index=True)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "city"], name="uniq_venue_name_city"),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"

    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    base_price = models.DecimalField(max_digits=8, decimal_places=2, validators=NON_NEGATIVE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PUBLISHED)
    tags = models.ManyToManyField(Tag, related_name="events", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at", "id"]
        indexes = [
            models.Index(fields=["starts_at"], name="event_starts_idx"),
            models.Index(fields=["venue", "starts_at"], name="event_venue_starts_idx"),
            models.Index(fields=["status", "starts_at"], name="event_status_starts_idx"),
        ]

    def __str__(self):
        return self.title


class Seat(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        BOOKED = "booked", "Booked"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seats")
    section = models.CharField(max_length=20)
    row = models.CharField(max_length=5)
    number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=NON_NEGATIVE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)

    class Meta:
        ordering = ["section", "row", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "section", "row", "number"], name="uniq_seat_per_event"
            ),
        ]
        indexes = [
            models.Index(fields=["event", "status"], name="seat_event_status_idx"),
        ]

    def __str__(self):
        return f"{self.section}-{self.row}{self.number}"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="bookings")
    seats = models.ManyToManyField(Seat, related_name="bookings")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"), validators=NON_NEGATIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "status"], name="booking_user_status_idx"),
            models.Index(fields=["event", "status"], name="booking_event_status_idx"),
        ]

    def __str__(self):
        return f"Booking {self.reference} ({self.status})"
