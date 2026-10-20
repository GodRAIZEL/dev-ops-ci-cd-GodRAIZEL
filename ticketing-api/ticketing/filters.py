import django_filters

from .models import Event


class EventFilter(django_filters.FilterSet):
    starts_after = django_filters.IsoDateTimeFilter(field_name="starts_at", lookup_expr="gte")
    starts_before = django_filters.IsoDateTimeFilter(field_name="starts_at", lookup_expr="lte")

    class Meta:
        model = Event
        fields = ["status", "venue", "tags"]
