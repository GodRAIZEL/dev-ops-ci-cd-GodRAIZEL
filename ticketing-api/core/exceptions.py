"""Standardised JSON error schema.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "status": 400, "details": {...}}}

``details`` is only present for validation errors (field -> list of messages).
"""
import logging

from django.db import IntegrityError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    415: "unsupported_media_type",
    429: "throttled",
}


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


def build_error(code, message, status_code, details=None):
    error = {"code": code, "message": message, "status": status_code}
    if details is not None:
        error["details"] = details
    return {"error": error}


def custom_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        message = "The resource is referenced by other records and cannot be deleted."
        return Response(build_error("conflict", message, 409), status=409)
    if isinstance(exc, IntegrityError):
        message = "The request violates a data integrity constraint."
        return Response(build_error("conflict", message, 409), status=409)

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled exception", exc_info=exc)
        return Response(build_error("server_error", "An unexpected error occurred.", 500),
                        status=500)

    code = ERROR_CODES.get(response.status_code, "error")
    details = None
    if isinstance(exc, ValidationError):
        code, message, details = "validation_error", "Request validation failed.", response.data
    elif isinstance(response.data, dict):
        message = str(response.data.get("detail", "Request failed."))
    else:
        message = "Request failed."
    response.data = build_error(code, message, response.status_code, details)
    return response
