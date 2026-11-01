# Phase 2A WAL recovery contract

The engine assumes one writer, integer or string keys, JSON-compatible values,
and a filesystem supporting file and directory `fsync`. Values retain JSON
semantics (for example, tuples serialize as arrays); this is not arbitrary
Python-object persistence. The data directory and its ancestors must already
be durably established for a power-loss durability claim.

`put()` appends one UTF-8 JSON line `["wal-v1", key, value]`, flushes the Python
buffer, synchronizes the WAL and its containing directory, then updates memory.
A successful return acknowledges this durable append; at the flush threshold,
Phase 2B.1 also completes synchronized SSTable publication and WAL retirement.
An append/synchronization failure propagates before memory is updated and marks
the WAL unusable for further appends until close/reopen. A failed operation may
nevertheless be present after recovery: failure is an unknown outcome, not a
rollback guarantee.

Initialization validates the WAL and replays operations into the MemTable in
file order, with the last operation for a key winning. Replay does not append,
flush the MemTable, or compact, even if recovered data exceeds the threshold.
Repeated recovery leaves a valid WAL unchanged.

Only newline-terminated records are replayed. An unterminated final line is
discarded, even if it contains syntactically complete JSON. Recovery truncates
that tail and synchronizes the repair before permitting another append.
Malformed newline-terminated records raise a line-numbered `ValueError`, even
at EOF; earlier corruption is never ignored because a torn tail follows it.
No tail repair is attempted until the preceding records have validated.
Initialization closes its WAL handle on recovery failure.

Legacy `key::JSON` lines remain readable; splitting uses only the first `::`.
Legacy decimal keys are interpreted as integers, matching the timestamp usage.
The old format irreversibly lost the distinction between numeric strings and
integers; nondecimal legacy keys remain strings. New records preserve that type
distinction and safely escape newlines and delimiters. There are no checksums:
corruption that still forms a valid record cannot be detected by this parser.

## Phase 2B.1 durability boundary

Phase 2B.1 supersedes the original unsafe flush boundary. SSTables are now
written and synchronized in temporary files, atomically published without
overwrite, and directory-synchronized before atomic WAL retirement. Failures
fence further writes until reopen. Automatic and explicit unsafe compaction are
disabled. See [SSTABLE_PUBLICATION.md](SSTABLE_PUBLICATION.md) for the ordering
proof, legacy-file policy, tests, and remaining limitations. WAL record encoding
and replay validation are unchanged.

Tests include real temporary files, abrupt process exit, replay ordering and key
types, repeated restarts, legacy input, torn-tail repair, malformed records,
synchronization errors, and interrupted publication/retirement. They do not
simulate machine power loss, faulty hardware, or concurrent writers. No empirical
power-loss safety or general compaction safety is claimed.
