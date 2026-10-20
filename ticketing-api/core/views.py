import time

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import build_error

STARTED_AT = time.monotonic()


class DatabaseHealthSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    vendor = serializers.CharField()


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    service = serializers.CharField()
    version = serializers.CharField()
    uptime_seconds = serializers.FloatField()
    timestamp = serializers.DateTimeField()
    database = DatabaseHealthSerializer()


class HealthView(APIView):
    """Liveness/readiness probe: database connectivity, uptime and service status."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses={200: HealthSerializer, 503: HealthSerializer},
        auth=[],
        tags=["health"],
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_ok = True
        except Exception:
            db_ok = False
        body = {
            "status": "ok" if db_ok else "degraded",
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
            "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
            "timestamp": timezone.now().isoformat(),
            "database": {"connected": db_ok, "vendor": connection.vendor},
        }
        return Response(body, status=200 if db_ok else 503)


def not_found(request, exception=None):
    message = "The requested resource was not found."
    return JsonResponse(build_error("not_found", message, 404), status=404)


def server_error(request):
    message = "An unexpected error occurred."
    return JsonResponse(build_error("server_error", message, 500), status=500)
