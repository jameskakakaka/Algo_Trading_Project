# Phase 2B.0: SSTable key and read correctness

The supported key domain remains exact Python integers and strings. MemTable
flush orders integers numerically before strings lexicographically, without
coercing keys. SSTable lookup compares both exact type and value, so integer
`2`, string `"2"`, and string `"02"` remain distinct. MemTable presence is checked
independently of value: a stored JSON null shadows an older SSTable value.
Public `get()` still returns None for both missing keys and stored null.
Boolean and floating-point lookups do not alias integer keys.

The WAL record format and recovery implementation are unchanged. SSTables
remain JSON arrays of [key, value] pairs; existing files are scanned without
rewriting or assuming their internal ordering. No legacy format migration or
key reinterpretation is performed. Legacy WAL numeric-string ambiguity remains
as described in WAL_RECOVERY.md.

## Phase 2B.1 update

Phase 2B.1 supersedes the original timestamp collision, publication, WAL
retirement, and new-table generation-order limitations. New files use numeric
generations, durable no-overwrite publication, and atomic WAL retirement.
Automatic compaction is disabled; Phase 2C supports explicit full compact().
Legacy merged-table provenance remains ambiguous; unsafe combinations fail
closed rather than silently selecting stale values. See
[SSTABLE_PUBLICATION.md](SSTABLE_PUBLICATION.md) for the complete contract.

The Phase 2B.0 regressions remain in place alongside Phase 2B.1 fault injection
and multi-generation tests. Neither suite establishes actual power-loss safety,
repairs legacy data loss. See [SSTABLE_COMPACTION.md](SSTABLE_COMPACTION.md)
for the separately tested full-compaction protocol.
