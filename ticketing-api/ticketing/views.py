from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.exceptions import Conflict
from core.permissions import AdminWriteOrReadOnly, BookingPermission, is_admin

from . import services
from .filters import EventFilter
from .models import Booking, Event, Seat, Tag, Venue
from .serializers import (
    BookingSerializer,
    BookingStatusSerializer,
    EventSerializer,
    SeatGenerateSerializer,
    SeatSerializer,
    TagSerializer,
    VenueSerializer,
)


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [AdminWriteOrReadOnly]
    search_fields = ["name", "city"]
    ordering_fields = ["name", "city", "capacity"]


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AdminWriteOrReadOnly]
    search_fields = ["name"]


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [AdminWriteOrReadOnly]
    filterset_class = EventFilter
    search_fields = ["title", "description", "venue__name", "venue__city"]
    ordering_fields = ["starts_at", "base_price", "created_at"]

    def get_queryset(self):
        queryset = (
            Event.objects.select_related("venue")
            .prefetch_related("tags")
            .annotate(
                seats_available=Count(
                    "seats", filter=Q(seats__status=Seat.Status.AVAILABLE), distinct=True
                )
            )
        )
        if not is_admin(self.request.user):
            queryset = queryset.exclude(status=Event.Status.DRAFT)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=SeatGenerateSerializer, responses={201: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"], url_path="generate-seats")
    def generate_seats(self, request, pk=None):
        """Bulk-create a block of seats (rows A, B, ...) for an event. Admin only."""
        event = self.get_object()
        serializer = SeatGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if event.seats.filter(section=data["section"]).exists():
            raise Conflict(f"Seats for section '{data['section']}' already exist.")
        count = data["rows"] * data["seats_per_row"]
        if event.seats.count() + count > event.venue.capacity:
            raise ValidationError({"detail": "Seat count would exceed venue capacity."})

        price = data.get("price", event.base_price)
        Seat.objects.bulk_create(
            Seat(event=event, section=data["section"], row=chr(ord("A") + row),
                 number=number + 1, price=price)
            for row in range(data["rows"])
            for number in range(data["seats_per_row"])
        )
        return Response({"created": count, "section": data["section"]},
                        status=status.HTTP_201_CREATED)


class SeatViewSet(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    permission_classes = [AdminWriteOrReadOnly]
    filterset_fields = ["event", "status", "section"]
    ordering_fields = ["section", "row", "number", "price"]


class BookingViewSet(viewsets.ModelViewSet):
    permission_classes = [BookingPermission]
    filterset_fields = ["status", "event"]
    ordering_fields = ["created_at", "total_amount"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        queryset = Booking.objects.select_related("event").prefetch_related("seats")
        if not is_admin(self.request.user):
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return BookingStatusSerializer
        return BookingSerializer

    def perform_destroy(self, instance):
        with transaction.atomic():
            if instance.status != Booking.Status.CANCELLED:
                services.release_seats(instance)
            instance.delete()

    @extend_schema(request=None, responses=BookingSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a booking you own (admins: any) and release its seats."""
        booking = services.change_booking_status(
            self.get_object(), Booking.Status.CANCELLED.value
        )
        return Response(BookingSerializer(booking, context=self.get_serializer_context()).data)
