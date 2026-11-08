# Phase 2C: explicit full SSTable compaction

## Contract and safety argument

Call `engine.compact()` explicitly under the existing single-writer model, with
no concurrent operations or external file mutations. Automatic compaction is
still disabled pending independent review. This phase introduces no manifest,
selective compaction, levels, background worker, WAL change, or MemTable change.
The filesystem and durable-directory prerequisites in SSTABLE_PUBLICATION.md
continue to apply.

Selection uses the same validated final filenames and ordering as reads. All
published tables participate, including redundant tables left by interrupted
compaction. Temporary files do not participate. Visit tables oldest to newest,
updating a dictionary indexed by exact (type, key) pairs. Only exact integer and
string keys are supported. Integer 2 and string "2" remain separate. Within one
table, preserve the first matching entry, as get() does, even for duplicate keys
in legacy input. Null is an ordinary value and shadows an older non-null value.
The output retains JSON arrays of pairs, sorted integers then strings.

The output v2 generation is one greater than the largest numeric filename suffix
of all inputs, including legacy identifiers. This exceeds every input generation
and orders above all legacy tables in the existing read path. Subsequent flushes
and compactions advance from the surviving v2 generation, independent of clocks.
An empty input set is a no-op; a single input is republished at a higher generation.

## Publication and cleanup

1. Validate and merge every input before changing any published name.
2. Write a unique same-directory `.sstable-*` temporary; flush, fsync, close.
3. Hard-link to the new v2 name. This is atomic and cannot overwrite a destination.
4. Fsync the directory before removing any input or the temporary alias.
5. Remove the temporary alias, then exactly the snapshotted input names, removing
   their in-memory Bloom filters after each successful unlink. The output has no
   cached Bloom filter and uses the normal uncached read path.
6. Fsync the directory again to persist cleanup.

Before durable publication all inputs remain intact. After durable publication,
the output contains the winning value for every key in every input and precedes
every input in reads. Any subset of surviving inputs is therefore redundant.
A crash during cleanup or loss of unsynchronized deletions can leave old names
visible; these cannot resurrect an old value, including beneath stored null.
This proves a manifest unnecessary for full compaction under this model.
The proof does not authorize selective compaction.

WAL replay still overlays every table through the MemTable. Compaction neither
retires nor copies WAL records, so a duplicate latest flush batch in the WAL and
any newer pending updates retain exactly their previous recovery precedence.

## Errors, compatibility, and limitations

Every error propagates and fences puts, flushes, and compactions until reopen.
There are no automatic retries, cleanup in exception handlers, or suppressed
cleanup errors. An operation that raises may already have published its output
or removed some inputs. Reopen discovers final filenames using existing rules;
it does not resume deletion automatically. A later explicit full compaction can
reclaim redundant published tables. Orphan temporary files remain ignored and
require operator cleanup while the engine is stopped. Repeated failures can
consume space. A collision fails without replacing the destination or retrying.

Plain legacy tables retain numeric timestamp ordering beneath v2 files. A sole
legacy merged table is accepted; combinations already rejected as ambiguous
remain rejected even if a newer v2 table exists. Unknown identities and duplicate
numeric generations fail closed. Malformed table arrays, entries, and unsupported
key types abort before publication; non-finite JSON values fail serialization.
There is no repair of lost legacy provenance, prior loss, external deletion, or
media corruption. No checksums, redundant storage, or multiwriter locking are
introduced. Stored null remains indistinguishable from absence through get().

Full merging holds input JSON and the merged dataset in memory and needs disk
space for the complete output before reclaiming inputs. Generation monotonicity
assumes published files are not externally removed/restored. Existing filesystem,
ancestor-directory durability, mutable-value, and hardware limitations remain.

Tests use real temporary directories, deterministic errors, and subprocess
os._exit boundaries before linking, after linking, after publication directory
sync, and after partial input deletion. They verify ordering, typed/null values,
WAL precedence, restart, collisions, and failed cleanup. These are process-crash
and API-failure tests, not actual power-loss tests.
