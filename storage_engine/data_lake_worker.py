

import json 
from kafka import KafkaConsumer 
from lsm_core import LSMTreeEngine 

# Defining the DataLakeWorker
class DataLakeWorker: 
    def __init__(self, topic='raw_market_data', bootstrap_servers=['localhost:9092']):
        print("Starting Data Lake Worker: Connect Kafka & LSM-Tree...")

        # Setup Kafka Consumer 
        self.consumer = KafkaConsumer(topic, bootstrap_servers=bootstrap_servers, auto_offset_reset='latest', value_deserializer=lambda m: json.loads(m.decode('utf-8')))

        # Starting the Core of Database 
        self.db = LSMTreeEngine(data_dir="./data")

    def start_listenting(self):
        print(f"Listening the data from Kafka Topic: '{self.consumer.subscription()}'...")

        try:
            for message in self.consumer:
                raw_candle = message.value

            # Extract the Key(Timestamp) and Value(PayLoad)
            key = int(raw_candle['timestamp'])
            value = raw_candle 

            # Write to the Database quickly
            self.db.put(key=key, value=value)

            print(f"[Data Lake] Saved the candle: {raw_candle['symbol']} - Giá: {raw_candle['close']} lúc {key}", end='\r')

        except KeyboardInterrupt: 
            print("\n Stopped the Data Lake Worker.") 