import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from train_pipeline import ModelTrainer

print("🔄 Fetching data and training model for Backtest...")
trainer = ModelTrainer(symbol="BTCUSDT", interval="1m")
raw_df = trainer.fetch_historical_data(limit=1000)
data_df = trainer.build_features_and_labels(raw_df)

feature_cols = ['RSI_14', 'MACD_hist', 'BB_high', 'BB_low', 'close', 'volume']
split_idx = int(len(data_df) * 0.8)

# --- SPLIT TRAIN & TEST ---
train_df = data_df.iloc[:split_idx].copy()
test_df = data_df.iloc[split_idx:].copy()

X_train = train_df[feature_cols]
y_train = train_df['target']

model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
model.fit(X_train, y_train)

# --- ENGINE BACKTEST ---
print("🔬 Running event-driven backtesting on Test Set...")

# 1. Model makes predictions based on current candle T
X_test = test_df[feature_cols]
test_df['prediction'] = model.predict(X_test)

# 2. Calculate Market Return for the NEXT candle (T to T+1)
# CRITICAL: We use shift(-1) because the trade executes after prediction at time T, 
# capturing the price movement of the upcoming period T+1.
test_df['market_return'] = test_df['close'].pct_change().shift(-1)

# 3. Calculate Strategy Return
# If prediction is 1 (UP), we capture the next candle's return. Else, we get 0.
test_df['strategy_return'] = np.where(test_df['prediction'] == 1, test_df['market_return'], 0)

# 4. Cumulative Returns (Assuming we start with 1.0 / 100%)
# fillna(0) handles the last row which gets NaN from shift(-1)
test_df['cum_market_return'] = (1 + test_df['market_return'].fillna(0)).cumprod()
test_df['cum_strategy_return'] = (1 + test_df['strategy_return'].fillna(0)).cumprod()

# --- PRINT METRICS ---
final_market = test_df['cum_market_return'].iloc[-1]
final_strategy = test_df['cum_strategy_return'].iloc[-1]
max_drawdown = (test_df['cum_strategy_return'] / test_df['cum_strategy_return'].cummax() - 1).min()

print("\n💰 --- SIMULATED TRADING RESULTS ---")
print(f"Buy & Hold Market Return: {(final_market - 1) * 100:.2f}%")
print(f"AI Strategy Return:       {(final_strategy - 1) * 100:.2f}%")
print(f"Maximum Drawdown:         {max_drawdown * 100:.2f}%")