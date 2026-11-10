"""IoT-specific error codes (PLAN 6.1). Subclass core errors so handlers stay shared."""

from __future__ import annotations

from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError, UnprocessableError


class DuplicateSerialError(ConflictError):
    error_code = "duplicate_serial"


class DuplicateLabelError(ConflictError):
    error_code = "duplicate_label"


class CommandPendingError(ConflictError):
    error_code = "command_pending"


class DeviceMismatchError(ForbiddenError):
    error_code = "device_mismatch"


class DeviceRemovedError(ForbiddenError):
    error_code = "device_removed"


class InvalidDeviceKeyError(UnauthorizedError):
    error_code = "invalid_key"


class InvalidThresholdError(UnprocessableError):
    error_code = "invalid_threshold"
