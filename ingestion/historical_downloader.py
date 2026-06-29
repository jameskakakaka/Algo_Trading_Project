import requests
import pandas as pd
import time
import os

class HistoricalDataDownloader:
    def __init__(self, symbol="BTCUSDT", interval="15m"):
        self.symbol = symbol
        self.interval = interval
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.limit = 1000 # Max allowed by Binance

    def download_bulk_data(self, total_candles=50000):
        print(f"📥 Starting bulk download: {total_candles} candles of {self.symbol} ({self.interval})...")
        
        all_data = []
        # Current time in milliseconds
        end_time = int(time.time() * 1000) 
        
        while len(all_data) < total_candles:
            params = {
                "symbol": self.symbol,
                "interval": self.interval,
                "limit": self.limit,
                "endTime": end_time
            }
            
            try:
                response = requests.get(self.base_url, params=params)
                response.raise_for_status()
                batch = response.json()
                
                if not batch:
                    print("\n⚠️ No more historical data found from Binance.")
                    break
                
                # Binance returns data from oldest to newest.
                # Since we use endTime, we are walking backwards in time.
                # We prepend the new batch to our accumulated data.
                all_data = batch + all_data
                
                # Update endTime for the next iteration: 
                # Timestamp of the oldest candle in the current batch minus 1 millisecond
                end_time = batch[0][0] - 1
                
                print(f"⏳ Downloaded {len(all_data)} / {total_candles} candles...", end="\r")
                
                # Sleep to respect Binance API rate limits
                time.sleep(0.2)
                
            except Exception as e:
                print(f"\n❌ API Error: {e}")
                break

        # Trim excess data if we fetched slightly more than requested
        all_data = all_data[-total_candles:]
        
        # Convert to Pandas DataFrame
        df = pd.DataFrame(all_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Strict Type Casting
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df['timestamp'] = df['timestamp'].astype(int)
        
        final_df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        # Save to CSV for offline training
        save_path = f"../{self.symbol}_{self.interval}_historical.csv"
        final_df.to_csv(save_path, index=False)
        
        print(f"\n✅ Successfully saved {len(final_df)} rows to {save_path}")
        return save_path

if __name__ == "__main__":
    downloader = HistoricalDataDownloader(symbol="BTCUSDT", interval="15m")
    # Fetch 50,000 candles (~520 days of 15m data)
    saved_file = downloader.download_bulk_data(total_candles=50000)