
import os
import json
import time
import re
import tempfile
import hashlib 


def _sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


# Adding Bloom Filter to the LSM-Tree Engine 
# Defining the Bloom Filter class 
class BloomFilter: 
    def __init__(self, size=1000, hash_count=3): # Size of the Bloom Filter, Number of hash functions
        self.size = size 
        self.hash_count = hash_count 
        # Initialize the bit array with 0s (bit array is a list of 0s with the size of the Bloom Filter)
        self.bit_array = [0] * size 
    
    def hashes(self, item): # Hasing the key to get the index of the bit array 
        """Create 3 hash values for 1 key"""
        hashes = []
        for i in range(self.hash_count):
            hash_hex = hashlib.md5((str(item) + str(i)).encode('utf-8')).hexdigest()
            # Convert the hash to an integer
            hashes.append(int(hash_hex, 16) % self.size) # % self.size to get the index of the bit array 
        return hashes 

    # Adding the key to the Bloom Filter 
    def add(self, item):
        for h in self.hashes(item):
            self.bit_array[h] = 1 # Set the bit to 1  

    # Checking to see if the item is in the Bloom Filter 
    def check(self, item):
        for h in self.hashes(item):
            if self.bit_array[h] == 0: # Set if the bit is 0, then the item is not available
                return False  
        return True 


# Write Ahead Log (WAL)
class WriteAheadLog:
    """Single-writer WAL for integer/string keys and JSON-compatible values.

    New records are ["wal-v1", key, value]; legacy key::JSON is readable
    (decimal legacy keys are interpreted as integers). Only newline-terminated
    records are committed. An unterminated tail is discarded, even if its JSON
    looks complete; malformed terminated records always raise ValueError.
    """
    def __init__(self, filepath):
        self.filepath = filepath
        # Open the file in append-only ('a')
        self.file = open(self.filepath, 'a', encoding='utf-8')
        self.failed = False

    def append(self, key, value):
        if self.failed:
            raise RuntimeError("WAL write previously failed; close and reopen the engine")
        if type(key) not in (int, str):
            raise TypeError("WAL keys must be integers or strings")
        log_entry = json.dumps(["wal-v1", key, value], allow_nan=False) + '\n'
        try:
            self.file.write(log_entry)
            self.file.flush()
            os.fsync(self.file.fileno())
            # Persist the WAL directory entry too (assumes an established data directory).
            directory_fd = os.open(os.path.dirname(os.path.abspath(self.filepath)), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            self.failed = True
            raise

    def replay(self):
        """Validate before repairing a torn tail; never append or flush MemTable."""
        records = []
        valid_end = 0
        torn_tail = False
        with open(self.filepath, 'rb') as source:
            for line_number, line in enumerate(source, 1):
                if not line.endswith(b'\n'):
                    torn_tail = True
                    break
                try:
                    text = line.decode('utf-8')
                    if text.startswith('['):
                        version, key, value = json.loads(text)
                        if version != 'wal-v1' or type(key) not in (int, str):
                            raise ValueError('unsupported WAL record')
                    else:
                        raw_key, raw_value = text.split('::', 1)
                        try:
                            key = int(raw_key)
                        except ValueError:
                            key = raw_key
                        value = json.loads(raw_value)
                    records.append((key, value))
                except (ValueError, UnicodeError) as error:
                    raise ValueError(f'Corrupt WAL record at line {line_number}') from error
                valid_end = source.tell()
        if torn_tail:
            with open(self.filepath, 'r+b') as repair:
                repair.truncate(valid_end)
                repair.flush()
                os.fsync(repair.fileno())
        return records

    def clear(self):
        """Atomically retire the WAL; caller must first durably publish its data."""
        directory = os.path.dirname(os.path.abspath(self.filepath))
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=directory,
                                             prefix='.wal-', delete=False) as empty:
                empty.flush()
                os.fsync(empty.fileno())
                temporary = empty.name
            self.file.close()
            os.replace(temporary, self.filepath)
            _sync_directory(directory)
            self.file = open(self.filepath, 'a', encoding='utf-8')
        except BaseException:
            self.failed = True
            raise

    def close(self):
        self.file.close()

# Creating the MemTable Class 
class MemTable:
    """MemTable: Data Structure on RAM, Organized with Timestamp"""
    def __init__(self, max_size=1000):
        self.table = {}
        self.max_size = max_size 
        self.current_size = 0

    def put(self, key, value):
        if key not in self.table:
            self.current_size += 1
        self.table[key] = value

    def get(self, key):
        return self.table[key] if self.contains(key) else None

    def contains(self, key):
        # Exclude bool/float aliases of integer keys as well as missing keys.
        return type(key) in (int, str) and key in self.table

    def get_sorted_entries(self):
        # Integers in numeric order, then strings in lexicographic order.
        return sorted(self.table.items(),
                      key=lambda item: (0 if type(item[0]) is int else 1, item[0]))

    def is_full(self):
        return self.current_size >= self.max_size

    def clear(self):
        self.table.clear()
        self.current_size = 0


# Setting up the LSMTreeEngine
class LSMTreeEngine:
    """The Brain combination of WAL & MemTable"""
    def __init__(self, data_dir="./data"):
        self.data_dir = data_dir
        self.failed = False
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.wal = WriteAheadLog(os.path.join(self.data_dir, "wal.log"))
        # LIMIT only 5 candles to flush 
        self.memtable = MemTable(max_size=5) 
        
        # Adding the Bloom Filter to the LSM-Tree Engine  
        # Each memtable has its own Bloom Filter  
        self.bloom_filters = {} 
        try:
            self._sstable_files()  # Validate identities before accepting writes.
            for key, value in self.wal.replay():
                self.memtable.put(key, value)
        except BaseException:
            self.wal.close()
            raise


    # Defining the put function (Write down the data to the LSM-Tree Engine)
    def put(self, key, value):
        """Acknowledge a synchronized WAL append and, when full, durable flush.

        Single writer only. Failed writes have an unknown recovery outcome.
        Reopen after a flush failure; recovery never flushes automatically.
        """
        if self.failed:
            raise RuntimeError("Flush previously failed; close and reopen the engine")
        # 1. Write to WAL
        self.wal.append(key, value)
        
        # 2. Write to MemTable on RAM
        self.memtable.put(key, value)
        
        # 3. Check the RAM 
        if self.memtable.is_full():
            self.flush_to_sstable()


    def _sstable_files(self):
        """Newest first; unknown/ambiguous legacy identities fail closed."""
        tables = []
        legacy = []
        for name in os.listdir(self.data_dir):
            if not (name.startswith('sstable_') and name.endswith('.json')):
                continue
            match = re.fullmatch(r'sstable_v2_([0-9]+)\.json', name)
            if match:
                tables.append(((1, int(match[1])), name))
                continue
            match = re.fullmatch(r'sstable_(merged_)?([0-9]+)\.json', name)
            if not match:
                raise ValueError(f'Unsupported SSTable identity: {name}')
            legacy.append((bool(match[1]), int(match[2]), name))
        if len(legacy) > 1 and any(merged for merged, _, _ in legacy):
            raise ValueError('Ambiguous legacy SSTable ordering; explicit migration required')
        tables.extend(((0, generation), name) for _, generation, name in legacy)
        identities = [identity for identity, _ in tables]
        if len(set(identities)) != len(identities):
            raise ValueError('Duplicate SSTable generation')
        return [name for _, name in sorted(tables, reverse=True)]

    def flush_to_sstable(self):
        """Publish a whole MemTable before retiring any WAL records.

        Atomic hard-link publication provides no-replace semantics on the same
        filesystem. Orphan temporary files are ignored, never recovered as tables.
        """
        if self.failed or self.wal.failed:
            raise RuntimeError("Storage previously failed; close and reopen the engine")
        if not self.memtable.current_size:
            return
        try:
            files = self._sstable_files()
            generations = [int(name[len('sstable_v2_'):-len('.json')])
                           for name in files if name.startswith('sstable_v2_')]
            generation = max(generations, default=0) + 1
            name = f'sstable_v2_{generation:020d}.json'
            path = os.path.join(self.data_dir, name)
            entries = self.memtable.get_sorted_entries()
            bloom_filter = BloomFilter(size=1000, hash_count=3)
            for key, _ in entries:
                bloom_filter.add(key)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.data_dir, prefix='.sstable-',
                                             delete=False) as temporary:
                json.dump(entries, temporary, indent=2, allow_nan=False)
                temporary.flush()
                os.fsync(temporary.fileno())
            # Unlike rename/replace, link cannot overwrite an existing destination.
            os.link(temporary.name, path)
            _sync_directory(self.data_dir)
            self.bloom_filters[name] = bloom_filter
            os.unlink(temporary.name)
            self.wal.clear()
            self.memtable.clear()
            # Automatic compaction remains disabled pending independent review.
        except BaseException:
            self.failed = True
            raise

    def get(self, key):
        """(Read Path)""" 
        # Check on RAM first 
        if self.memtable.contains(key):
            print(f"🔍 [LSM Engine] Found in MemTable: {key}")
            return self.memtable.get(key)
        # Checking on SSTable files 
        # Explicit generations, newest first; temporary files are excluded.
        sstable_files = self._sstable_files()
        
        # Checking on the Bloom Filter 
        for file_name in sstable_files:
            bf = self.bloom_filters.get(file_name) # Getting the Bloom Filter for the file 

            if bf and not bf.check(key):
                print(f"🔍 [LSM Engine] Not found in Bloom Filter: {file_name}")
                continue 

            print(f"🔍 [LSM Engine] Might be Found in SSTable: {file_name}")
            # Reading the file 
            file_path = os.path.join(self.data_dir, file_name)
            with open(file_path, 'r') as f: 
                data = json.load(f)
                for item_key, item_value in data:
                    if type(item_key) is type(key) and item_key == key:
                        print(f"🔍 [LSM Engine] Found in SSTable: {file_name}")
                        return item_value 
        print(f"🔍 [LSM Engine] Not found in any SSTable: {key}")
        return None 



    def compact(self):
        """Durably summarize all published tables, then remove their names.

        Single writer, no concurrent operations. Surviving inputs after a crash
        are redundant beneath the newer output. WAL and MemTable are untouched.
        Any failure requires reopen; uncertain operations are never retried here.
        """
        if self.failed or self.wal.failed:
            raise RuntimeError("Storage previously failed; close and reopen the engine")
        try:
            files = self._sstable_files()
            if not files:
                return
            merged = {}
            for name in reversed(files):
                with open(os.path.join(self.data_dir, name), encoding='utf-8') as source:
                    data = json.load(source)
                if not isinstance(data, list):
                    raise ValueError(f'Invalid SSTable entries: {name}')
                table = {}
                for entry in data:
                    if not isinstance(entry, list) or len(entry) != 2:
                        raise ValueError(f'Invalid SSTable entry: {name}')
                    key, value = entry
                    if type(key) not in (int, str):
                        raise ValueError(f'Unsupported SSTable key: {name}')
                    # get() returns the first matching entry within a table.
                    table.setdefault((type(key), key), value)
                merged.update(table)
            entries = sorted(((key, value) for (_, key), value in merged.items()),
                             key=lambda item: (0 if type(item[0]) is int else 1, item[0]))
            generation = max(int(re.search(r'([0-9]+)\.json$', name)[1])
                             for name in files) + 1
            name = f'sstable_v2_{generation:020d}.json'
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.data_dir, prefix='.sstable-',
                                             delete=False) as temporary:
                json.dump(entries, temporary, indent=2, allow_nan=False)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.link(temporary.name, os.path.join(self.data_dir, name))
            _sync_directory(self.data_dir)
            # Nothing below may run until the output name and data are durable.
            os.unlink(temporary.name)
            for old_name in files:
                os.unlink(os.path.join(self.data_dir, old_name))
                self.bloom_filters.pop(old_name, None)
            _sync_directory(self.data_dir)
        except BaseException:
            self.failed = True
            raise


if __name__ == "__main__":
    print("🚀 Running LSM-Tree Database...")
    db = LSMTreeEngine()
    
    # Simulate Kafka Consumer to push candles to DB
    print("Streaming data into the Engine...")
    
    # Write down 12 candles
    keys_to_test = []
    for i in range(1, 18):
        fake_timestamp = 1700000000000 + (i * 60000) # Key
        keys_to_test.append(fake_timestamp)
        fake_candle = {"open": 100, "close": 100 + i, "volume": 10} # Value
        
        print(f"Write {i} candles to MemTable...")
        db.put(key=fake_timestamp, value=fake_candle)
        # Read the newest candle (RAM)
        db.get(keys_to_test[-1])
        # Read the oldest candle (File Merged)
        db.get(keys_to_test[0])
        # Read the trash 
        db.get(9999999999999)
        time.sleep(0.05)
