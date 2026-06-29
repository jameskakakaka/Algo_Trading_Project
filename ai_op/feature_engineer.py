# Importing libraries
import json
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from kafka import KafkaConsumer
from collections import deque


# Defining the Streaming Feature
class StreamingFeatureEngineer:
    def __init__(self, window_size=50):
        self.data_window = deque(maxlen=window_size)
        
    def add_candle_and_extract_features(self, raw_candle):
        self.data_window.append(raw_candle)
        
        # 35s of waiting for MACD to run smoothly
        if len(self.data_window) < 35: 
            return None
            
        df = pd.DataFrame(list(self.data_window))
        
        # --- FEATURE ENGINEERING ---
        
        # 1. Calculating RSI (14 loops)
        rsi_indicator = RSIIndicator(close=df['close'], window=14)
        df['RSI_14'] = rsi_indicator.rsi()
        
        # 2. Calculating MACD (12, 26, 9)
        macd_indicator = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD_line'] = macd_indicator.macd()
        df['MACD_signal'] = macd_indicator.macd_signal()
        df['MACD_hist'] = macd_indicator.macd_diff() # Histogram
        
        # 3. Calculating Bollinger Bands (20, 2)
        bb_indicator = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_high'] = bb_indicator.bollinger_hband()
        df['BB_low'] = bb_indicator.bollinger_lband()
        
        # Drop NA candles
        df.dropna(inplace=True)
        
        if df.empty:
            return None
            
        # Extract Features from the newest candles
        latest_features = df.iloc[-1].to_dict()
        return latest_features

if __name__ == "__main__":
    print("🧠 AI Brain restarting...")
    
    consumer = KafkaConsumer(
        'raw_market_data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='latest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    engineer = StreamingFeatureEngineer(window_size=50)
    
    print("⏳ Fetching candles...")
    
    for message in consumer:
        raw_candle = message.value
        features = engineer.add_candle_and_extract_features(raw_candle)
        
        if features:
            print("\n🔥 NEW singal ready:")
            print(f"Close: {features['close']}")
            print(f"RSI (14): {features['RSI_14']:.2f}")
            print(f"MACD Hist: {features['MACD_hist']:.4f}")
            print(f"BB High: {features['BB_high']:.2f} | BB Low: {features['BB_low']:.2f}")
        else:
            print(f"Fetching candles: {len(engineer.data_window)}/35...", end="\r")