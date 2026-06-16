from dataclasses import dataclass
from typing import Any


@dataclass
class FailureMode:
    id: str
    name: str
    description: str
    category: str   # network | dependency | data | resource


# ── The complete failure mode library ────────────────────────────────────────

FAILURE_MODES: list[FailureMode] = [

    # Network failures
    FailureMode("http_timeout", "HTTP Timeout",
                "Outbound HTTP request to a dependency hangs and never responds",
                "network"),

    FailureMode("connection_refused", "Connection Refused",
                "Dependency service is down — TCP connection refused",
                "network"),

    FailureMode("dns_failure", "DNS Resolution Failure",
                "Dependency hostname cannot be resolved",
                "network"),

    FailureMode("slow_response", "Slow Response (5s delay)",
                "Dependency responds but takes 5 seconds — tests timeout handling",
                "network"),

    FailureMode("connection_reset", "Connection Reset",
                "TCP connection is reset mid-transfer",
                "network"),

    # Dependency failures
    FailureMode("http_500", "Dependency 500 Error",
                "External service returns Internal Server Error",
                "dependency"),

    FailureMode("http_429", "Rate Limited (429)",
                "External service returns Too Many Requests",
                "dependency"),

    FailureMode("http_503", "Service Unavailable (503)",
                "External service temporarily unavailable",
                "dependency"),

    FailureMode("http_401", "Unauthorized (401)",
                "External service rejects credentials",
                "dependency"),

    FailureMode("http_404", "Dependency Not Found (404)",
                "External service endpoint no longer exists",
                "dependency"),

    # Data failures
    FailureMode("malformed_json", "Malformed JSON Response",
                "Dependency returns invalid JSON that cannot be parsed",
                "data"),

    FailureMode("empty_response", "Empty Response Body",
                "Dependency returns 200 OK but with an empty body",
                "data"),

    FailureMode("wrong_content_type", "Wrong Content-Type",
                "Dependency returns HTML instead of JSON",
                "data"),

    FailureMode("partial_response", "Partial/Truncated Response",
                "Response body is cut off mid-transfer",
                "data"),

    FailureMode("null_fields", "Null Required Fields",
                "Dependency returns JSON with required fields set to null",
                "data"),

    # Resource failures
    FailureMode("db_connection_drop", "Database Connection Drop",
                "Database connection is lost mid-request",
                "resource"),

    FailureMode("db_timeout", "Database Query Timeout",
                "Database query takes too long and times out",
                "resource"),

    FailureMode("db_constraint_violation", "DB Constraint Violation",
                "Database rejects insert/update due to constraint",
                "resource"),
]

FAILURE_MODE_MAP = {f.id: f for f in FAILURE_MODES}


def get_failure_mode(failure_id: str) -> FailureMode | None:
    return FAILURE_MODE_MAP.get(failure_id)


def get_failures_by_category(category: str) -> list[FailureMode]:
    return [f for f in FAILURE_MODES if f.category == category]
