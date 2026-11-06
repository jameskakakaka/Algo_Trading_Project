"""Synthetic single-writer local benchmark. No HFT or production claim."""
import argparse
import contextlib
import io
import json
import platform
import tempfile
import time
from pathlib import Path
from storage_engine.lsm_core import LSMTreeEngine


def benchmark(records=200):
    if not 10 <= records <= 10000:
        raise ValueError('benchmark records must be in [10,10000]')
    with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
        engine = LSMTreeEngine(directory)
        try:
            engine.memtable.max_size = 32
            start = time.perf_counter()
            for i in range(records):
                engine.put(i, {'close': str(100+i), 'source': 'synthetic'})
            write_s = time.perf_counter()-start
            start = time.perf_counter()
            engine.flush_to_sstable()
            flush_s = time.perf_counter()-start
            files_before = len(list(Path(directory).glob('sstable*')))
            start = time.perf_counter()
            for i in range(records):
                assert engine.get(i)['close'] == str(100+i)
            read_s = time.perf_counter()-start
            start = time.perf_counter()
            engine.compact()
            compact_s = time.perf_counter()-start
        finally:
            engine.wal.close()
        start = time.perf_counter()
        engine = LSMTreeEngine(directory)
        restart_s = time.perf_counter()-start
        engine.wal.close()
        return dict(platform=platform.platform(), python=platform.python_version(),
                    cpu=platform.processor(), logical_cpus=__import__('os').cpu_count(),
                    storage='TemporaryDirectory on local filesystem; mount/hardware unspecified',
                    concurrency=1, memtable_threshold=32, synthetic_records=records, write_s=write_s,
                    writes_per_s=records/write_s, read_mean_s=read_s/records,
                    explicit_flush_s=flush_s, compaction_s=compact_s, restart_s=restart_s,
                    tables_before=files_before, tables_after=len(list(Path(directory).glob('sstable*'))),
                    disk_bytes=sum(p.stat().st_size for p in Path(directory).iterdir()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.records), indent=2))


if __name__ == '__main__':
    main()
