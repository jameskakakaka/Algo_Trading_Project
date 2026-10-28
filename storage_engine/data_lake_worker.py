

import json 
if __package__:
    from .lsm_core import LSMTreeEngine
else:
    from lsm_core import LSMTreeEngine

# Defining the DataLakeWorker
class DataLakeWorker: 
    def __init__(self, topic='raw_market_data', bootstrap_servers=['localhost:9092']):
        from kafka import KafkaConsumer

        print("Starting Data Lake Worker: Connect Kafka & LSM-Tree...")

        # Setup Kafka Consumer 
        self.consumer = KafkaConsumer(topic, bootstrap_servers=bootstrap_servers, auto_offset_reset='latest', value_deserializer=lambda m: json.loads(m.decode('utf-8')))

        # Starting the Core of Database 
        try:
            self.db = LSMTreeEngine(data_dir="./data")
        except BaseException as initialization_error:
            try:
                self.consumer.close()
            except Exception as cleanup_error:
                raise initialization_error from cleanup_error
            raise

    def start_listenting(self):
        try:
            print(f"Listening the data from Kafka Topic: '{self.consumer.subscription()}'...")
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
        finally:
            try:
                self.consumer.close()
            finally:
                self.db.wal.close()


def main():
    worker = DataLakeWorker()
    worker.start_listenting()


if __name__ == "__main__":
    main()
