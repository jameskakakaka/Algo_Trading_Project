# Finalized market bar contract v1 — Phase 3A.1

This module is opt-in, pure Python, and uses only the standard library. It does
not change any existing producer, consumer, storage, trading, or training path.

## Exact schema

Every field below is required. Unknown fields are rejected. Validation returns a
fresh canonical dictionary and never mutates its input. Failures raise
`BarValidationError`, a `ValueError` subclass.

| Field | Type and invariant |
| --- | --- |
| schema_version | Strict integer `1`; booleans and floats rejected |
| event_type | String `market.bar.finalized` |
| event_id | Canonical identity string defined below |
| exchange | String, normalized to `binance` only |
| market | String, normalized to `spot` only |
| symbol | Uppercase ASCII alphanumeric string, length 2–32 |
| timeframe | Case-sensitive string `1m` or `15m` |
| open_time_ms | Strict integer Unix milliseconds, UTC interval aligned |
| end_time_ms | Strict integer, exclusive end = open + interval duration |
| is_final | Boolean `true` only |
| open, high, low, close | Finite decimal strings; strictly positive |
| volume | Finite decimal string; nonnegative base-asset volume |
| observed_at_ms | Strict integer; at least end_time_ms |
| published_at_ms | Strict integer; at least observed_at_ms |
| source | Lowercase ASCII token matching `[a-z][a-z0-9_]{0,63}` |

Non-ASCII identifier inputs are rejected before whitespace trimming or case
conversion, including Unicode letters that would case-convert into ASCII.
Identifiers trim outer ASCII whitespace and, except timeframe, normalize case. Symbols
are syntactically validated; this module does not verify an exchange listing.
Sources identify provenance, not authority. Timeframe case is never folded (`1M`
is not `1m`). Required constants are checked, not silently repaired.

## Identity, timestamps, and storage encoding

Identity is `(exchange, market, symbol, timeframe, open_time_ms)`.
The event ID joins these canonical components with `:`. Component alphabets
exclude `:`, and the integer has one canonical spelling, so this encoding is
injective without hashes or escaping. Example:

`binance:spot:BTCUSDT:1m:1800000000000`

The storage identity is `bar:v1:` followed by that event ID. It is a string key,
not a timestamp or a guarantee of a storage index/range scan. Neither metadata
nor OHLCV changes identity. Different symbols, intervals, or opens do.

All four timestamps must lie in the fixed interval
`946684800000 <= timestamp < 4102444800000` (2000-01-01 through before 2100-01-01
UTC). This explicit v1 domain rejects contemporary seconds and microseconds;
units cannot be inferred universally from an arbitrary integer. No wall-clock
freshness test is performed. Dates outside this domain require contract revision.

Bars cover `[open_time_ms, end_time_ms)`. UTC alignment is modulo 60,000 for 1m
and 900,000 for 15m. There is no local timezone, DST, or calendar-month support.
Binance's inclusive close timestamp must be converted by a future adapter;
passing it directly fails validation. Operational times need not be aligned.
The metadata invariant is `end <= observed <= published`; equality is allowed.

## Exact decimal canonicalization and serialization

OHLCV accepts only strings containing ASCII decimal notation, optionally a sign,
fraction, or exponent. No floats, integers, whitespace, separators, NaN, or
Infinity are accepted. Input length is limited to 256 characters and the parsed
Decimal exponent magnitude to 256, bounding expansion. Values are parsed with
`decimal.Decimal` and formatted without arithmetic normalization or rounding.
Canonical output uses plain notation, removes redundant fractional zeros and
leading plus/zeros, and maps signed zero to `0`. Price zero is then rejected.
`low <= open <= high` and `low <= close <= high` are required.

`canonical_json` validates, sorts keys, and emits compact JSON with decimal
strings intact. JSON load/validate/serialize is stable. Full-event JSON differs
when metadata differs; it is not a market-content fingerprint.

## Public functions

```python
from schemas.data_types import (
    validate_finalized_bar, normalize_supported_value, normalize_decimal,
    generate_event_id, storage_identity, canonical_json,
    market_content_equal, operational_metadata_equal, classify_bar_events,
)
```

- `validate_finalized_bar(event)` returns a canonical JSON-compatible dict.
- `normalize_supported_value(field, value)` normalizes identifier strings only.
- `normalize_decimal(value)` canonicalizes decimal syntax; field sign checks
  belong to event validation.
- `generate_event_id(exchange, market, symbol, timeframe, open_time_ms)` checks
  identity components and UTC alignment; it does not validate an entire event.
- `storage_identity(event)` validates the complete event and returns its key.
- `canonical_json(event)` returns deterministic JSON text.
- `market_content_equal(a, b)` validates both and compares identity, end time,
  and OHLCV. Operational fields are excluded.
- `operational_metadata_equal(a, b)` validates both and compares observation,
  publication, and source only. This does not imply equal identity or content.
- `classify_bar_events(existing, candidate)` returns `distinct`, `duplicate`, or
  `conflict`. Existing must be valid. Candidate must satisfy validation except
  that a differing end boundary for the same identity is reported as conflict.
  The candidate's actual end must still be a strict integer in the v1 timestamp
  domain. For this exception only, metadata is checked against the end derived
  from open time and timeframe: `expected_end <= observed <= published`, rather
  than the candidate's changed end. Thus a changed end beyond observation time
  is a conflict, but observation before the expected end or publication before
  observation still raises `BarValidationError`. All unrelated validation rules
  remain enforced. For a distinct identity the candidate must pass full
  validation, including its actual end boundary. Invalid existing bars, malformed
  candidate fields, and invalid distinct candidates raise `BarValidationError`
  rather than returning a classification. Neither input is mutated.
  Classification never authorizes storing an invalid candidate;
  `validate_finalized_bar` always enforces the full original contract.

Same identity and canonical market content is a duplicate even if observation,
publication, or source differs. Same identity with changed OHLCV or end time is a
conflict. Callers must quarantine/reconcile conflicts rather than overwrite.
These stateless helpers do not persist deduplication state or provide ordering,
gap detection, processing idempotency, or exactly-once delivery.

## Finality trust boundary and migration

`is_final=true` is a required assertion, not evidence of exchange finality.
Even plausible post-end metadata can be fabricated. Validation does not prove
that the response was fetched after close, that exchange clocks agree, or that
history will never be corrected. Phase 3A.2 must implement post-close selection,
clock uncertainty/safety delay, response normalization, pagination, continuity,
overlap handling, and explicit incomplete/failure outcomes. No such selection
is implemented here. Kafka recovery remains a separate later phase.

The legacy live payload uses float OHLCV and `timestamp` rather than
`open_time_ms`; historical CSV omits identity and metadata. Neither is accepted
implicitly. Lost decimal precision or finality cannot be recovered by relabeling
old payloads. A future adapter must retain exchange decimal strings and supply
verified stream context. Existing consumers require explicit timestamp mapping
and ML numeric conversion. Timestamp-only storage keys require migration and
cannot reconstruct already overwritten cross-stream data. The default 15m
training versus 1m live mismatch remains unresolved. No legacy module imports
this contract, and no legacy behavior changes in Phase 3A.1.

## Offline verification

`python3 -B -m unittest discover -s tests -v`

The contract tests need no Kafka, Docker, exchange access, or third-party package.
They cover schema, identity, timestamps, decimals, boundaries, metadata,
duplicates/conflicts, serialization, and stable storage keys.
