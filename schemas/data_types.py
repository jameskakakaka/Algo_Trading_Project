"""Pure v1 finalized-bar contract. Validation cannot prove exchange finality.

See MARKET_BAR_V1.md. No legacy float/timestamp payload conversion is implicit.
"""

import json
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

INTERVAL_MS = {"1m": 60_000, "15m": 900_000}
MIN_TIME_MS = 946684800000  # 2000-01-01 UTC, inclusive
MAX_TIME_MS = 4102444800000  # 2100-01-01 UTC, exclusive
IDENTITY_FIELDS = ("exchange", "market", "symbol", "timeframe", "open_time_ms")
PRICE_FIELDS = ("open", "high", "low", "close", "volume")
MARKET_FIELDS = IDENTITY_FIELDS + ("end_time_ms",) + PRICE_FIELDS
OPERATIONAL_FIELDS = ("observed_at_ms", "published_at_ms", "source")
REQUIRED_FIELDS = frozenset(
    MARKET_FIELDS + OPERATIONAL_FIELDS
    + ("schema_version", "event_type", "event_id", "is_final")
)


class BarValidationError(ValueError):
    """An event does not satisfy the v1 contract."""


def normalize_supported_value(field, value):
    """Normalize supported identifiers; never coerce non-string values.

    Timeframes remain case-sensitive. Sources are lowercase ASCII tokens.
    Symbols are uppercase ASCII alphanumerics, not an exchange listing lookup.
    """
    if type(value) is not str:
        raise BarValidationError(f"{field}: expected string")
    if not value.isascii():
        raise BarValidationError(f"{field}: expected ASCII identifier input")
    value = value.strip()
    if field == "symbol":
        value = value.upper()
        valid = re.fullmatch(r"[A-Z0-9]{2,32}", value)
    elif field in ("exchange", "market"):
        value = value.lower()
        valid = value == {"exchange": "binance", "market": "spot"}[field]
    elif field == "timeframe":
        valid = value in INTERVAL_MS
    elif field == "source":
        value = value.lower()
        valid = re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value)
    else:
        raise BarValidationError(f"unsupported normalization field: {field}")
    if not valid:
        raise BarValidationError(f"{field}: unsupported value")
    return value


def _timestamp(field, value):
    if type(value) is not int or not MIN_TIME_MS <= value < MAX_TIME_MS:
        raise BarValidationError(f"{field}: expected integer Unix ms in [2000, 2100)")
    return value


def normalize_decimal(value):
    """Return an exact plain decimal string without context-dependent rounding."""
    if type(value) is not str or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value
    ):
        raise BarValidationError("OHLCV: expected finite decimal string")
    # Bound expansion and input size to avoid unbounded exponent allocation.
    if len(value) > 256:
        raise BarValidationError("OHLCV: decimal input exceeds 256 characters")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise BarValidationError("OHLCV: decimal exponent out of range") from error
    if not number.is_finite() or abs(number.as_tuple().exponent) > 256:
        raise BarValidationError("OHLCV: invalid decimal exponent")
    if number == 0:
        return "0"
    result = format(number, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def generate_event_id(exchange, market, symbol, timeframe, open_time_ms):
    """Derive an injective identity from normalized, delimiter-free components."""
    values = [normalize_supported_value(k, v) for k, v in zip(
        IDENTITY_FIELDS[:4], (exchange, market, symbol, timeframe)
    )]
    _timestamp("open_time_ms", open_time_ms)
    if open_time_ms % INTERVAL_MS[values[3]]:
        raise BarValidationError("open_time_ms: not aligned to UTC interval")
    return ":".join(values + [str(open_time_ms)])


def validate_finalized_bar(event):
    """Validate and return a fresh canonical JSON-compatible dict.

    Unknown fields are rejected. Identifier case/whitespace and decimal spelling
    are normalized; event_id must already match the resulting canonical identity.
    No clock, network, state, or caller mutation is involved.
    """
    return _validate_bar(event, check_end=True)


def _validate_bar(event, *, check_end):
    if not isinstance(event, Mapping):
        raise BarValidationError("event: expected mapping")
    if set(event) != REQUIRED_FIELDS:
        raise BarValidationError("event: missing or unknown fields")
    result = dict(event)
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise BarValidationError("schema_version: expected integer 1")
    if type(result["event_type"]) is not str or result["event_type"] != "market.bar.finalized":
        raise BarValidationError("event_type: expected market.bar.finalized")
    if result["is_final"] is not True:
        raise BarValidationError("is_final: expected boolean true")
    for field in (*IDENTITY_FIELDS[:4], "source"):
        result[field] = normalize_supported_value(field, result[field])
    for field in ("open_time_ms", "end_time_ms", "observed_at_ms", "published_at_ms"):
        _timestamp(field, result[field])
    expected_id = generate_event_id(*(result[k] for k in IDENTITY_FIELDS))
    if type(result["event_id"]) is not str or result["event_id"] != expected_id:
        raise BarValidationError("event_id: does not match canonical identity")
    if check_end and result["end_time_ms"] != result["open_time_ms"] + INTERVAL_MS[result["timeframe"]]:
        raise BarValidationError("end_time_ms: incompatible exclusive boundary")
    if not result["end_time_ms"] <= result["observed_at_ms"] <= result["published_at_ms"]:
        raise BarValidationError("timestamps: require end <= observed <= published")
    for field in PRICE_FIELDS:
        result[field] = normalize_decimal(result[field])
        if Decimal(result[field]) < 0 or (field != "volume" and Decimal(result[field]) == 0):
            raise BarValidationError(f"{field}: invalid sign or zero price")
    low, high = Decimal(result["low"]), Decimal(result["high"])
    if not all(low <= Decimal(result[k]) <= high for k in ("open", "close")):
        raise BarValidationError("OHLC: require low <= open, close <= high")
    return result


def canonical_json(event):
    """Serialize validated content with stable key order and no insignificant spaces."""
    return json.dumps(validate_finalized_bar(event), sort_keys=True, separators=(",", ":"), allow_nan=False)


def storage_identity(event):
    """Return a version-prefixed collision-safe string key for a validated bar."""
    return "bar:v1:" + validate_finalized_bar(event)["event_id"]


def market_content_equal(left, right):
    """Compare canonical identity, boundaries and OHLCV, ignoring metadata."""
    a, b = validate_finalized_bar(left), validate_finalized_bar(right)
    return all(a[k] == b[k] for k in MARKET_FIELDS)


def operational_metadata_equal(left, right):
    """Compare observation/publication/source only, independently of identity."""
    a, b = validate_finalized_bar(left), validate_finalized_bar(right)
    return all(a[k] == b[k] for k in OPERATIONAL_FIELDS)


def classify_bar_events(left, right):
    """Compare a valid existing bar with an incoming candidate.

    A changed end boundary for the same identity is classified as conflict even
    though that candidate cannot pass standalone validation. Other malformed
    fields raise. Distinct candidates must pass full validation.
    """
    a = validate_finalized_bar(left)
    b = _validate_bar(right, check_end=False)
    if any(a[k] != b[k] for k in IDENTITY_FIELDS):
        validate_finalized_bar(right)
        return "distinct"
    return "duplicate" if all(a[k] == b[k] for k in MARKET_FIELDS) else "conflict"
