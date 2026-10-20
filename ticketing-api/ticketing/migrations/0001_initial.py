import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Venue",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("city", models.CharField(db_index=True, max_length=80)),
                ("capacity", models.PositiveIntegerField(
                    validators=[django.core.validators.MinValueValidator(1)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="venue",
            constraint=models.UniqueConstraint(
                fields=("name", "city"), name="uniq_venue_name_city"),
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("starts_at", models.DateTimeField()),
                ("base_price", models.DecimalField(
                    decimal_places=2, max_digits=8,
                    validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("published", "Published"),
                             ("cancelled", "Cancelled")],
                    default="published", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_events", to=settings.AUTH_USER_MODEL)),
                ("tags", models.ManyToManyField(
                    blank=True, related_name="events", to="ticketing.tag")),
                ("venue", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="events", to="ticketing.venue")),
            ],
            options={"ordering": ["starts_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["starts_at"], name="event_starts_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["venue", "starts_at"], name="event_venue_starts_idx"),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(fields=["status", "starts_at"], name="event_status_starts_idx"),
        ),
        migrations.CreateModel(
            name="Seat",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("section", models.CharField(max_length=20)),
                ("row", models.CharField(max_length=5)),
                ("number", models.PositiveIntegerField(
                    validators=[django.core.validators.MinValueValidator(1)])),
                ("price", models.DecimalField(
                    decimal_places=2, max_digits=8,
                    validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("status", models.CharField(
                    choices=[("available", "Available"), ("booked", "Booked")],
                    default="available", max_length=10)),
                ("event", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="seats", to="ticketing.event")),
            ],
            options={"ordering": ["section", "row", "number"]},
        ),
        migrations.AddConstraint(
            model_name="seat",
            constraint=models.UniqueConstraint(
                fields=("event", "section", "row", "number"), name="uniq_seat_per_event"),
        ),
        migrations.AddIndex(
            model_name="seat",
            index=models.Index(fields=["event", "status"], name="seat_event_status_idx"),
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("confirmed", "Confirmed"),
                             ("cancelled", "Cancelled")],
                    default="pending", max_length=12)),
                ("total_amount", models.DecimalField(
                    decimal_places=2, default=Decimal("0.00"), max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="bookings", to="ticketing.event")),
                ("seats", models.ManyToManyField(
                    related_name="bookings", to="ticketing.seat")),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="bookings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["user", "status"], name="booking_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["event", "status"], name="booking_event_status_idx"),
        ),
    ]
