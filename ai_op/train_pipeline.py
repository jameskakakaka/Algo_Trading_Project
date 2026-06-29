# Importing the libraries
import pandas as pd
import requests
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, accuracy_score


# Defining the class models.
class ModelTrainer:
    def __init__(self, symbol="BTCUSDT", interval="1m"):
        self.symbol = symbol
        self.interval = interval
        
    def fetch_historical_data(self, limit=1000):
        """Fetch bulk data history from Binance API (Max100candles)"""
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": self.symbol, "interval": self.interval, "limit": limit}
        response = requests.get(url, params=params)
        raw_data = response.json()
        
        df = pd.DataFrame(raw_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Parse the data type
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df['timestamp'] = df['timestamp'].astype(int)
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    def build_features_and_labels(self, df):
        """Calculating the features"""
        
        # 1. Calcuating the features (Data Streaming)
        df['RSI_14'] = RSIIndicator(close=df['close'], window=14).rsi()
        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD_hist'] = macd.macd_diff()
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_high'] = bb.bollinger_hband()
        df['BB_low'] = bb.bollinger_lband()
        
        # 2. LABELING: Prediciting next increase / decrease
        # IF the next closing value (shift -1) > current closing value -> Then = increase, opposite is close (0)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        # Dropping the NA values
        df.dropna(inplace=True)
        return df

    def train(self):
        print("📥 Fetching 1000 historical datas of candles...")
        raw_df = self.fetch_historical_data(limit=1000)
        
        print("⚙️ Building features and lables...")
        data_df = self.build_features_and_labels(raw_df)
        
        # Identify what to make decisions/predictions about for AI learning
        feature_cols = ['RSI_14', 'MACD_hist', 'BB_high', 'BB_low', 'close', 'volume']
        
        X = data_df[feature_cols]
        y = data_df['target']
        
        # --- TIME-SERIES DATA SPLIT ---
        # Taking 80% of far history to train, 20% of recent to test
        split_idx = int(len(X) * 0.8)
        
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        print(f"🏋️ Running the training model of XGBCModel {len(X_train)}...")
        model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
        model.fit(X_train, y_train)
        
        # --- ĐÁNH GIÁ MODEL ---
        predictions = model.predict(X_test)
        acc = accuracy_score(y_test, predictions)
        
        print("\n📊 --- CHECKING THE ACCURYT OF THE AI BRAIN ---")
        print(f"OVERALL ACCURACY (Accuracy): {acc * 100:.2f}%")
        print("\nDetails of Classification Report (Classification Report):")
        print(classification_report(y_test, predictions))
        
        # Return model after finishing training
        return model

if __name__ == "__main__":
    trainer = ModelTrainer(symbol="BTCUSDT", interval="1m")
    trained_model = trainer.train()