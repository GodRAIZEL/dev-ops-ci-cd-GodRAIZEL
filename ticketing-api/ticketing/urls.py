from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, EventViewSet, SeatViewSet, TagViewSet, VenueViewSet

router = DefaultRouter()
router.register("venues", VenueViewSet, basename="venue")
router.register("tags", TagViewSet, basename="tag")
router.register("events", EventViewSet, basename="event")
router.register("seats", SeatViewSet, basename="seat")
router.register("bookings", BookingViewSet, basename="booking")

urlpatterns = router.urls
