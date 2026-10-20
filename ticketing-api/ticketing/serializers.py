from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from . import services
from .models import Booking, Event, Seat, Tag, Venue


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "city", "capacity", "created_at"]
        read_only_fields = ["created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]


class EventSerializer(serializers.ModelSerializer):
    seats_available = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "venue", "title", "description", "starts_at", "base_price", "status",
            "tags", "seats_available", "created_by", "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_seats_available(self, obj):
        value = getattr(obj, "seats_available", None)
        if value is None:  # instance not loaded through the annotated queryset
            value = obj.seats.filter(status=Seat.Status.AVAILABLE).count()
        return value

    def validate_starts_at(self, value):
        if self.instance is None and value <= timezone.now():
            raise serializers.ValidationError("Event start time must be in the future.")
        return value


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ["id", "event", "section", "row", "number", "price", "status"]

    def validate(self, attrs):
        if self.instance is None:
            event = attrs["event"]
            if event.seats.count() >= event.venue.capacity:
                raise serializers.ValidationError("Venue capacity reached for this event.")
        return attrs


class SeatGenerateSerializer(serializers.Serializer):
    section = serializers.CharField(max_length=20)
    rows = serializers.IntegerField(min_value=1, max_value=26)
    seats_per_row = serializers.IntegerField(min_value=1, max_value=100)
    price = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=0, required=False
    )


class BookingSerializer(serializers.ModelSerializer):
    seat_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        allow_empty=False,
        max_length=services.MAX_SEATS_PER_BOOKING,
    )
    seats = SeatSerializer(many=True, read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "reference", "user", "event", "seat_ids", "seats", "status",
            "total_amount", "created_at", "updated_at",
        ]
        read_only_fields = ["reference", "status", "total_amount", "created_at", "updated_at"]

    def validate_seat_ids(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate seat ids are not allowed.")
        return value

    def validate_event(self, event):
        if event.status != Event.Status.PUBLISHED:
            raise serializers.ValidationError("Event is not open for booking.")
        if event.starts_at <= timezone.now():
            raise serializers.ValidationError("Event has already started.")
        return event

    def create(self, validated_data):
        return services.create_booking(
            user=self.context["request"].user,
            event=validated_data["event"],
            seat_ids=validated_data["seat_ids"],
        )


class BookingStatusSerializer(serializers.Serializer):
    """Admin-only status change (confirm / cancel); responds with the full booking."""

    status = serializers.ChoiceField(choices=Booking.Status.choices)

    def update(self, instance, validated_data):
        return services.change_booking_status(instance, validated_data["status"])

    def to_representation(self, instance):
        return BookingSerializer(instance, context=self.context).data
