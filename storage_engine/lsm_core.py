
import os
import json
import time
import glob
import hashlib 


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
    """WAL: Save the Log into RAM to prevent loss from crashing"""
    def __init__(self, filepath):
        self.filepath = filepath
        # Open the file in append-only ('a')
        self.file = open(self.filepath, 'a')

    def append(self, key, value):
        # Format: key::value\n
        log_entry = f"{key}::{json.dumps(value)}\n"
        self.file.write(log_entry)
        self.file.flush() # Tell the function to write down in the disk 

    def clear(self):
        self.file.close()
        open(self.filepath, 'w').close() # Clear the file 
        self.file = open(self.filepath, 'a')

    def close(self):
        self.file.close()

# Creating the MemTable Class 
class MemTable:
    """MemTable: Data Structure on RAM, Organized with Timestamp"""
    class MemTable:
    def __init__(self, max_size=1000):
        self.table = {}
        self.max_size = max_size 
        self.current_size = 0

    def put(self, key, value):
        if key not in self.table:
            self.current_size += 1
        self.table[key] = value

    def get(self, key):
        return self.table.get(key, None)

    def get_sorted_entries(self):
        return sorted(self.table.items())

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
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.wal = WriteAheadLog(os.path.join(self.data_dir, "wal.log"))
        # LIMIT only 5 candles to flush 
        self.memtable = MemTable(max_size=5) 
        
        # Adding the Bloom Filter to the LSM-Tree Engine  
        # Each memtable has its own Bloom Filter  
        self.bloom_filters = {} 


    # Defining the put function (Write down the data to the LSM-Tree Engine)
    def put(self, key, value):
        """(Write Path)"""
        # 1. Write to WAL
        self.wal.append(key, value)
        
        # 2. Write to MemTable on RAM
        self.memtable.put(key, value)
        
        # 3. Check the RAM 
        if self.memtable.is_full():
            self.flush_to_sstable()


    # Flushing to SSTable
    def flush_to_sstable(self):
        """Flush the Data from RAM to the Disk  (SSTable)"""
        timestamp = int(time.time() * 1000)

        # Differentiate the file name to save the Key for Dict 
        sstable_name = f"sstable_{timestamp}.json"

        # The path for sstable 
        sstable_path = os.path.join(self.data_dir, f"sstable_{timestamp}.json")
        
        # Take the data sorted from RAM 
        sorted_data = self.memtable.get_sorted_entries()

        # Create a Bloom Filter for new file  
        bf = BloomFilter(size=1000, hash_count=3)
        
        # Write down to RAM (SSTable as JSON)
        with open(sstable_path, 'w') as f:
            json.dump(sorted_data, f, indent=2)

        for key, _ in sorted_data:
            bf.add(key)
    
        # Set the sstable_name
        self.bloom_filters[sstable_name] = bf


        print(f"💾 [LSM Engine] Flushed {len(sorted_data)} to: {sstable_path}")
        
        # Delete the RAM and WAL after writing 
        self.memtable.clear()
        self.wal.clear()


        # --- COMPACTION IF NECESSARY ---
        self.compact()

    def get(self, key):
        """(Read Path)""" 
        # Check on RAM first 
        val = self.memtable.get(key)
        if val is not None:
            print(f"🔍 [LSM Engine] Found in MemTable: {key}")
            return val
        # Checking on SSTable files 
        # Scanning through from the oldest to the newest 
        sstable_files = sorted([f for f in os.listdir(self.data_dir) if f.startswith("sstable_")], reverse=True)
        
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
                    if int(item_key) == int(key):
                        print(f"🔍 [LSM Engine] Found in SSTable: {file_name}")
                        return item_value 
        print(f"🔍 [LSM Engine] Not found in any SSTable: {key}")
        return None 



    # Defining the compact
    def compact(self):
        """
        The process of gathering all the SSTable files into 1 group
        """
        # Look for all the current SSTable files 
        search_pattern = os.path.join(self.data_dir, "sstable_*.json")
        sstable_files = [f for f in glob.glob(search_pattern) if "merged" not in f]

        # Up to 3 files then start to gather 
        if len(sstable_files) >= 3:
            print(f"⚙️ [COMPACTION] Starting to gathering {len(sstable_files)} small files...")
            
            merged_data = {}

            # Read all the files 
            for file_path in sstable_files:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        key, value = item[0], item[1]
                        # Dictionary automatically write on old data with new data if the same key
                        merged_data[key] = value 
                        
            # Organizing the files with TimeStamp
            sorted_merged_data = sorted(merged_data.items())
            
            # Lưu ra file Merged lớn
            timestamp = int(time.time() * 1000)
            merged_filename = os.path.join(self.data_dir, f"sstable_merged_{timestamp}.json")
            with open(merged_filename, 'w') as f:
                json.dump(sorted_merged_data, f, indent=2)
            print(f"✅ [COMPACTION] Successfully grouped to: {merged_filename}")

            # Create the Bloom Filter for the file merged
            merged_bf = BloomFilter(size = 1000, hash_count=3)
            for k, _ in sorted_merged_data:
                merged_bf.add(k)
            self.bloom_filters[merged_filename] = merged_bf


            # Cleaning all the previous small files and delete the old Bloom Filter on RAM 
            for file_path in sstable_files:
                old_filename = os.path.basename(file_path) # Set the origin
                if old_filename in self.bloom_filters:
                    del self.bloom_filters[old_filename] # Clean the RAM
                os.remove(file_path) # Cleam SStable 


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