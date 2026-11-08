# Phase 2D storage lifecycle reliability report

## Scope and result

Inspected both storage Python modules, all five existing test modules, the four
storage contracts, and the project README. Baseline: 52 tests passed. Production
storage code is unchanged: no reproducible production bug was found. Final
validation: **55 tests passed in 19.486 seconds**, including 58 new fault
scenarios (56 matrix cases and 2 partial/complete WAL-write cases). New tests
use only Python's standard library, real temporary directories, and the existing
single-writer API. No services, dependencies, commits, or pushes are involved.

The new suite is `tests/test_storage_lifecycle.py`. The full run's actual unittest
output is checked in as [PHASE2D_TEST_OUTPUT.txt](PHASE2D_TEST_OUTPUT.txt).
Environment: Python 3.12.3, Linux 6.6.87.2-microsoft-standard-WSL2, x86_64.
The baseline test-harness development uncovered a test counter error (a loop
variable was incremented between before/after threshold-fsync cases). This was
fixed in the test harness before final validation; it was not a storage bug.

## Reproduce and diagnose

From the repository root:

```bash
python3 -B -m unittest discover -s tests -p test_storage_lifecycle.py -v
python3 -B -m unittest discover -s tests -v
```

To capture the full suite as done for this report (read-path prints go to stdout):

```bash
python3 -B -m unittest discover -s tests -v > /tmp/phase2d-read-stdout.log 2> storage_engine/PHASE2D_TEST_OUTPUT.txt
```

Seeds: **0, 1, 7, 42, 73, 101, 2025, 65537**. Each executes **300 generated
steps**, totaling **2,400**. Every step checks the entire latest-state model.
The output records per-seed operation counts. `overwrite` executes two puts;
`extra-put` counts the second separately and is not another generated step.
Each seed also executes a fixed tail: two puts, five reopens, two compactions,
and one flush (10 API calls). Model-check reads, internal threshold flushes,
setup, and fault-recovery operations are excluded from generated-step counts.
Across all seeds: 693 put steps, 348 overwrite steps (696 puts), 338 gets,
348 flushes, 326 compactions, and 347 reopens; 2,748 generated API calls
including the 348 second overwrites, plus 80 fixed-tail API calls.

Random choices include puts, reads, flushes, compactions, restarts, and repeated
overwrites; values include null, nested arrays/objects, booleans, numbers, and
Unicode strings. Keys include matching integer/string forms, negatives, a large
integer, empty strings, leading zeros, delimiters, newlines, and Unicode.
Failures identify seed, zero-based step index, operation counts, and the exact
executed operation prefix. Re-run the named test with the documented seeds;
there are no wall-clock seeds or optional packages.

## Model and invariants

The acknowledged model is a Python dictionary with original int/string keys,
updated only after put returns. Test inputs are JSON-compatible and are never
mutated outside put. A failed put does not modify that model. Its attempted key
is checked against exactly two allowed recovery outcomes: previous value/absence
or attempted latest value. All other keys must match the acknowledged model
exactly. A separate selected recovery state is checked through three reopens,
then superseded by a new acknowledged put, flush, compaction, and restart.
An observed uncertain value is never relabeled as an acknowledgment.

Public get results are checked alongside a test-only presence oracle that merges
v2 JSON tables in independently computed numeric generation order and overlays
MemTable entries. This detects lost stored-null entries even though get returns
None for both null and absence. Exact `(type, key)` sets are also compared.
The oracle is intentionally scoped to fresh test-created v2 directories;
existing tests retain responsibility for legacy/corrupt/ambiguous input handling.

Checks cover newest-write-wins, typed identity, acknowledged state preservation,
WAL replay before and after compaction, repeated restart, and continued operation
after recovery. Every workload put forbids implicit compact calls. Successful
compactions preserve WAL bytes, MemTable contents, and size. Failed compactions
are checked for the same preservation. Surviving published inputs retain their
bytes; existing collision tests verify publication cannot overwrite or retry.
Every injected I/O error must propagate, and subsequent put/flush/compact calls
must reject without changing any file until reopen.

## Fault-injection matrix

`test_fault_matrix` runs every row before and after the real operation:
**28 boundaries × 2 = 56 isolated scenarios**. Each case starts with three
published generations, typed/null updates in the WAL, and a full model.
Threshold cases have four distinct pending keys; their failed fifth-key put is
uncertain. WAL append cases attempt to overwrite an acknowledged disk value.
Each hook must be reached and produce the expected exception; injections are
removed before closing/reopening. No automatic retry is performed.

| Boundary | New scenarios | Existing complementary coverage |
| --- | --- | --- |
| WAL write, buffer flush, file fsync, directory fsync | put: 4 × 2 | acknowledged writes followed by abrupt process exit |
| SSTable serialization, file fsync | explicit flush + threshold put + compact: 2 × 3 × 2 | pre-publication errors, malformed compaction input |
| Atomic hard-link publication | all three: 3 × 2 | collision no-overwrite tests for flush/compact; subprocess exits before/after link |
| Publication directory fsync | all three: 3 × 2 | deletion-order assertions; subprocess exit after compaction publication sync |
| Temporary alias unlink | all three: 3 × 2 | ignored/preserved orphan files |
| Empty replacement WAL fsync | flush + threshold: 2 × 2 | retirement ordering and restart tests |
| Atomic WAL replacement | flush + threshold: 2 × 2 | abrupt process exit after replacement |
| WAL retirement directory fsync | flush + threshold: 2 × 2 | published table plus old/empty WAL recovery |
| First and second compaction input deletion | compact: 2 × 2 | subprocess exit after partial deletion |
| Compaction cleanup directory fsync | compact: 1 × 2 | redundant input recovery and explicit recompaction |

Additionally, `test_partial_wal_write_is_uncertain_and_tail_repair_is_stable`
runs **2 scenarios**: an unterminated partial overwrite is discarded on recovery;
a complete newline-terminated record whose write raises is recovered. Both fence
all mutations and preserve unrelated acknowledged typed/null values through
restarts and subsequent writes. This explicitly exercises unknown outcome,
rather than assuming an exception rolls back a write.

Fsync occurrences are scoped to each tested operation: flush has table,
publication directory, empty WAL, retirement directory; compact has output,
publication directory, cleanup directory. Threshold puts add two preceding WAL
syncs. Existing ordering tests complement these positional hooks and will expose
protocol changes requiring matrix updates.

## Limits

These are deterministic API-failure and process-crash tests. The new error tests
reopen after closing the WAL; existing subprocess tests supply abrupt-exit
coverage. They do not verify hardware power loss, device cache behavior, kernel
crashes, every possible short write, disk-full behavior, media corruption,
concurrent writers, or filesystems that violate the documented atomicity/fsync
assumptions. Finite seeds do not prove all possible histories. Directory and
ancestor durability and the existing immutable-caller-value contract remain
prerequisites. Orphan cleanup remains an operator task.

## Git change summary

Three added files: the 275-line lifecycle test, this report, and the 69-line
actual unittest output. No existing file changed. `git diff --check` passed;
new-file whitespace was also checked independently. No commits or pushes.
