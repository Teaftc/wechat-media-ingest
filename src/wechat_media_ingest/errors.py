from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    CAPTCHA = "CAPTCHA"
    DELETED = "DELETED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    MEDIA_EXPIRED = "MEDIA_EXPIRED"
    NETWORK = "NETWORK"
    INTEGRITY = "INTEGRITY"
    PARSE_ERROR = "PARSE_ERROR"
    UNSUPPORTED = "UNSUPPORTED"


EXIT_OK = 0
EXIT_PARTIAL = 10
EXIT_JOB_FAILED = 20
EXIT_INTEGRITY = 30
EXIT_ENVIRONMENT = 40


@dataclass
class IngestError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
