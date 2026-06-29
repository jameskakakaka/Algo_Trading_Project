
# Importing the libraries
import json 
import pandas as pd 
from collections import deque
import joblib 
from ta.momentum import RSIIndicator 
from ta.trend import MACD, EMAIndicator 
from ta.volatility import BollingerBands, AverageTrueRange 
from kafka import KafkaConsumer 


# Setting up the Paper Trading Bot
class LiveTradingBot:
    def __init__(self, model_path="../ai_op/xgboost_trading_brain.pkl", window_size=60):
        print(f"Starting the AI brain from{model_path}...")
        self.model = joblib.load(model_path)

        # Saving the 60 recent candles to calculate the late signal such as EMA50
        self.data_window = deque(maxlen=window_size)
        
        # List of features to match the training 
        self.feature_cols = [
            'RSI_14', 'MACD_hist', 'BB_high', 'BB_low', 
            'Dist_to_EMA50', 'ATR_14', 'close', 'volume'
        ]

        # Monitoring the changing of the state (sold or not sold)
        self.in_position = False 

    # Defining the gathering and predicting candles 
    def add_candle_and_predict(self, raw_candle):
        self.data_window.append(raw_candle)

        # Minimum of 50 candles to calculate the EMA50
        if len(self.data_window) < 50:
            return None 

        df = pd.DataFrame(list(self.data_window))

        # --- FEATURE ENGINEERING --- 
        df['RSI_14'] = RSIIndicator(close=df['close'], window=14).rsi()

        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD_hist'] = macd.macd_diff()
        
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_high'] = bb.bollinger_hband()
        df['BB_low'] = bb.bollinger_lband()

        df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['Dist_to_EMA50'] = (df['close'] - df['EMA_50']) / df['EMA_50'] * 100
        
        df['ATR_14'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

        # Extracting from the newest range 
        latest_features = df.iloc[-1]

        # Preventing NaN 
        if latest_features.isna().any():
            return None 

        # Setting the array 2D for XGBoost
        X_live = pd.DataFrame([latest_features[self.feature_cols]])

        # The giving decision 
        prediction = self.model.predict(X_live)[0]
        probability = self.model.predict_proba(X_live)[0][1] # Probability of AI into buying

        self.execute_trade(prediction, probability, latest_features['close'], latest_features['timestamp'])
    
    # The Trading phase
    def execute_trade(self, prediction, probability, current_price, timestamp):
        """Executing the trading (Paper Trading)"""
        print(f"\n[{timestamp}] 📊 Analyze the price: ${current_price:.2f} | AI Confidence (Increase): {probability*100:.1f}%")
        
        # Chiến lược giao dịch đơn giản:
        if prediction == 1 and not self.in_position:
            print("🟢 [Signal] AI nhận định giá TĂNG. Thực hiện: MUA VÀO (OPEN LONG) 🚀")
            self.in_position = True
            
        elif prediction == 0 and self.in_position:
            print("🔴 [Signal] AI nhận định giá GIẢM. Thực hiện: BÁN RA (CLOSE LONG / TAKE PROFIT) 💰")
            self.in_position = False
            
        else:
            state = "HOLDING" if self.in_position else "NOT EXECUTING"
            print(f"⚪ [Signal] Không có thay đổi. Trạng thái: {state} ⏳")

if __name__ == "__main__":
    print("🔥 KHỞI ĐỘNG HỆ THỐNG GIAO DỊCH TỰ ĐỘNG END-TO-END 🔥")
    
    # Đảm bảo đường dẫn tới file pkl là chính xác
    bot = LiveTradingBot(model_path="../ai_op/xgboost_trading_brain.pkl")
    
    # Kết nối vào hệ thống Data Streaming của chúng ta
    consumer = KafkaConsumer(
        'raw_market_data',
        bootstrap_servers=['localhost:9092'],
        auto_offset_reset='latest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    print("📡 Đang lắng nghe luồng dữ liệu từ Kafka... Chờ thu thập đủ 50 nến để tính EMA50.")
    
    for message in consumer:
        raw_candle = message.value
        bot.add_candle_and_predict(raw_candle)