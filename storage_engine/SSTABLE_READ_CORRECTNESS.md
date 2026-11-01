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

## Remaining limitations (outside this patch)

- SSTable filenames use millisecond timestamps: flushes can collide and overwrite
  files. Reverse lexicographic filename order is not a reliable generation order,
  especially across merged and unmerged files; reads can select stale versions.
- Compaction still uses filesystem enumeration order to overwrite duplicate keys,
  and native sorting of mixed integer/string keys can raise TypeError. Its merged
  Bloom filter is registered under a full path while reads use basenames. These
  existing behaviors are unchanged; this patch does not make compaction safe.
- SSTables are written directly without atomic publication or synchronization,
  followed by MemTable clearing and WAL truncation. Crashes or I/O errors during
  this handoff can lose acknowledged data or leave malformed files. Compaction
  likewise writes output and deletes inputs without a crash-safe protocol.
- There is no manifest, checksum validation, or multiwriter coordination. Bloom
  filters share hashes for some distinct key types; exact lookup prevents false
  matches, but hash collisions remain possible as expected for Bloom filters.

Regression tests use real TemporaryDirectory storage and avoid compaction and
multiple competing SSTable generations. They verify one mixed-key flush and
restart, exact key identity, nonnumeric strings, null shadowing (including WAL
replay), missing keys, and unchanged legacy SSTable bytes. They do not establish
full storage durability, correct generation precedence, or power-loss safety.
