from django.contrib import admin

from .models import Booking, Event, Seat, Tag, Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "capacity")
    search_fields = ("name", "city")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "venue", "starts_at", "status", "base_price")
    list_filter = ("status", "venue")
    search_fields = ("title",)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("event", "section", "row", "number", "price", "status")
    list_filter = ("status",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "event", "status", "total_amount", "created_at")
    list_filter = ("status",)
    readonly_fields = ("reference",)
