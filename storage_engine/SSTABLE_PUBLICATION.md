# Phase 2B.1: atomic publication and WAL retirement

## Model and invariants

One engine/writer, with no concurrent calls, owns a data directory. The local
filesystem must support same-filesystem atomic hard links, atomic replacement,
and meaningful file/directory fsync. The directory and ancestors must already
be durably established. No other process may mutate the files.

A successful put synchronizes a newline-terminated WAL record before modifying
memory. Threshold-triggered puts also complete the flush before returning.
Failures propagate and have unknown commit outcome; they are not rollbacks.
I1/I3 hold across process restart within this model: each acknowledged latest
key value is represented in the WAL or a published table. Overwritten historical
values are not a version-history API.

I2: WAL retirement follows synchronized table publication. I4: publication never
overwrites a destination. I5: only recognized final table identities participate
in reads/generation discovery. I6: unchanged WAL replay preserves exact int/str
identity and last-write-wins ordering. I7: replayed WAL values overlay tables,
including null, so duplicate latest batches are safe. I8: numeric generations
order new tables across repeated flushes and restarts.

## Protocol and crash boundaries

1. Snapshot the MemTable in typed-key order. Choose one plus the largest visible
   v2 generation (or 1). Create a unique `.sstable-*` temporary in the same data
   directory. Write the existing JSON array-of-pairs representation, flush the
   Python buffer, fsync the file, and close it.
2. Atomically hard-link it to `sstable_v2_<20-digit-generation>.json`. Hard-link
   publication is the no-overwrite equivalent of rename: an existing destination
   raises FileExistsError. No pre-check/replace race can overwrite published data.
3. Fsync the directory. Only now is the table considered durably published for
   purposes of retiring the WAL. Unlink the temporary alias.
4. Create a unique `.wal-*` empty file in the same directory, flush and fsync it,
   close the old WAL handle, and atomically replace `wal.log`. Fsync the directory
   and reopen the append handle. Only then clear the MemTable.

Before step 3, the original WAL is untouched. A process crash after linking but
before directory sync can leave a visible table plus the WAL; replay is safe.
Under the stated filesystem ordering assumptions, loss of an unsynchronized
publication still leaves the synchronized WAL. After step 3, either old WAL or
empty replacement may survive an interrupted retirement, but the table already
contains every retired value. Atomic WAL replacement avoids a partially
truncated/malformed WAL. No checkpoint offsets or manifest are needed because
flush retires the entire single-writer WAL, including all recovered entries.

Any flush error fences writes and further flushes until close/reopen. This is
necessary even after WAL replacement: the old append handle might be closed or
refer to an obsolete inode. Memory is retained on error. Append failures retain
the Phase 2A failed-WAL behavior and also prevent flush. Startup never flushes
replayed records. It ignores orphan temporary files without deleting them;
operators may reclaim them while the engine is stopped. Repeated failures may
consume disk space. A new flush after recovery can publish duplicate data in a
higher generation safely.

## Compatibility and compaction boundary

WAL bytes and replay format are unchanged. SSTable contents remain JSON pairs;
only new final filenames encode explicit generations. Existing files are never
rewritten. Plain legacy `sstable_<timestamp>.json` files sort by numeric timestamp
and all new generations take precedence over legacy tables. A sole legacy merged
table is readable. Multiple legacy tables involving a merged table fail closed:
legacy compaction discarded the provenance needed to establish key precedence.
Unknown final SSTable identities and duplicate numeric generations also fail
closed. Such directories require an explicit, separately reviewed migration.
Prior data loss, collisions, or incorrect compaction cannot be repaired here.

Automatic compaction has been removed. Explicit compact() raises
NotImplementedError until Phase 2C. Tables accumulate; this trades space/read
cost for retaining all published inputs. No general compaction safety is claimed.

## Verification and limits

The unittest suite uses real TemporaryDirectory files, deterministic failures
at serialization, table fsync, hard-link publication, publication directory
sync, WAL replacement, and WAL file/directory sync. It checks preserved WAL
bytes, same-process fencing, reopen recovery, collisions, repeated generations,
newest-wins, typed keys/null, temporary-file isolation, and compaction fencing.
Subprocess os._exit tests stop immediately after hard-link publication and WAL
replacement. These test process crashes, not actual power loss or device caches.

The synchronization protocol relies on the filesystem honoring fsync and atomic
operations. No empirical power-loss guarantee is claimed. Unsupported filesystems
must fail rather than use an unsafe fallback. There are no checksums, redundancy,
media-corruption repair, multiwriter locks, or transactional multi-key API.
Malformed legacy/final JSON can raise on reads; ambiguous legacy state fails at
startup. A missing externally deleted table cannot be reconstructed after WAL
retirement. Mutable in-memory values retain the existing API semantics; callers
must not mutate stored objects outside put(). Directory/ancestor creation is
not made durable by this phase. Disk exhaustion and orphan cleanup remain
operational concerns. General compaction remains deferred to Phase 2C.
