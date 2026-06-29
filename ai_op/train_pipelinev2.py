
# Importing the libraries 
import pandas as pd
import os
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib # Save model after training 

# Identify the ModelTrainer 
class AdvancedModelTrainer:
    def __init__(self, data_path="../BTCUSDT_15m_historical.csv"):
        self.data_path = data_path 

    def load_offline_data(self):
        """
        Pushing the data from loaded CSV file
        """
        if not os.path.exists(self.data_path):
        # Locate the current directory if ran in the wrong root
            fallback_path = self.data_path.replace("../", "")
            if os.path.exists(fallback_path):
                self.data_path = fallback_path
            else:
                raise FileNotFoundError(f"Did not locate the file at {self.data_path}!")
        print(f"📂 Pushing data from {self.data_path}...")
        df = pd.read_csv(self.data_path)
        return df

    def build_features_and_labels(self, df): 
        """
        Identifying the features 
        """
        print("⚙️ Calculating...")
        
        # 1. Momentum & Trend 
        df['RSI_14'] = RSIIndicator(close=df['close'], window=14).rsi()
        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD_hist'] = macd.macd_diff()
        
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['BB_high'] = bb.bollinger_hband()
        df['BB_low'] = bb.bollinger_lband()
        
        # 2. Navigate Trend (EMA) và Changes (ATR)
        # Calculating the distant from the current value to EMA50
        df['EMA_50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['Dist_to_EMA50'] = (df['close'] - df['EMA_50']) / df['EMA_50'] * 100
        
        # ATR to see the changes of candles
        df['ATR_14'] = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
        
        # 3. Label (LABELING)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        df.dropna(inplace=True)
        return df

    def train(self):
        raw_df = self.load_offline_data()
        data_df = self.build_features_and_labels(raw_df)
        
        # Update the features for AI to learn 
        feature_cols = [
            'RSI_14', 'MACD_hist', 'BB_high', 'BB_low', 
            'Dist_to_EMA50', 'ATR_14', 'close', 'volume'
        ]
        
        X = data_df[feature_cols]
        y = data_df['target']
        
        # Time-series Split (80/20)
        split_idx = int(len(X) * 0.8)
        
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        print(f"🏋️ Đang train XGBoost với {len(X_train)} nến (Khung 15m)...")
        # Upgrade max_depth up to 5 for model to learn more complex pattern
        model = XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train)
        
        # Evaluate 
        predictions = model.predict(X_test)
        acc = accuracy_score(y_test, predictions)
        
        print("\n📊 --- Evaluate the assessment of AI ---")
        print(f"Accurracy (Accuracy): {acc * 100:.2f}%")
        print("\nDetails (Classification Report):")
        print(classification_report(y_test, predictions))
        
        # --- Lưu bộ não AI lại thành file để dùng cho Live Trading ---
        model_path = "xgboost_trading_brain.pkl"
        joblib.dump(model, model_path)
        print(f"💾 Save the model at: {model_path}")
        
        return model, data_df, feature_cols

if __name__ == "__main__":
    trainer = AdvancedModelTrainer(data_path="../BTCUSDT_15m_historical.csv")
    trained_model, processed_data, features = trainer.train()
                

         