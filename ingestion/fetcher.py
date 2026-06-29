

# Importing libraries 
from ensurepip import bootstrap
import requests
import json 
import time 
from kafka import KafkaProducer

# Defining the Extracting from the Binance
class BinanceDataFetcher:
    def __init__(self, symbol="BTCUSDT", interval="1m"):
        self.symbol = symbol
        self.interval = interval 
        self.base_url = "https://api.binance.com/api/v3/klines"
    
    def fetch_recent_klines(self, limit=5): # Setting the fetching 
        """
        Fetching the data (OHLCV) frin Binance API.
        Binance returning lists then we map them into Schema
        """
    
        params = {
            "symbol": self.symbol,
            "interval": self.interval,
            "limit": limit 
        }

        try:
            response = requests.get(self.base_url, params = params)
            response.raise_for_status() # Look for errors API 
            raw_data = response.json()

            structured_data = []

            # Looking through the Data fetched from API and Type Casting
            for kline in raw_data:
                payload = {
                    "symbol": self.symbol,
                    "timestamp": int(kline[0]),       # Unix Epoch Time (ms) -Int64 
                    "open": float(kline[1]),          # Open - Float64
                    "high": float(kline[2]),          # High - Float64
                    "low": float(kline[3]),           # Low - Float64
                    "close": float(kline[4]),         # Close - Float64
                    "volume": float(kline[5]),        # Volume - Float64
                    "timeframe": self.interval
                }
                structured_data.append(payload)
                
            return structured_data 

        except Exception as e:
            print(f"Error while fetching form Binance:{e}")

if __name__ == "__main__":
    print("🚀 Starting Ingestion Service...")
    
    # Initialize Kafka Producer
    # value_serializer => naking sure all the dictionary are parsed as JSON and encode UTF-8
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    fetcher = BinanceDataFetcher(symbol="BTCUSDT", interval="1m")
    TOPIC_NAME = 'raw_market_data'
    
    print(f"📡 Start the streaming to topic: {TOPIC_NAME}...")
    
    # Loop for extracting the canldes
    try:
        while True:
            recent_data = fetcher.fetch_recent_klines(limit=1) # Taking the recent 
            if recent_data:
                data_point = recent_data[0]
                # Extract data to kafka 
                producer.send(TOPIC_NAME, value=data_point)
                print(f"✅ Pushed: {data_point['symbol']} - Deal: {data_point['close']} At {data_point['timestamp']}")
            
            time.sleep(2) # Đợi 2 giây rồi gọi lại API
            
    except KeyboardInterrupt:
        print("\n🛑 Stop Streaming")
    finally:
        producer.close()


