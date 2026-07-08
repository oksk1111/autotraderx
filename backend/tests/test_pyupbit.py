import pyupbit
import time

markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]
intervals = ["minute60", "minute15", "minute5"]

print("Testing pyupbit.get_ohlcv...")

for market in markets:
    for interval in intervals:
        try:
            df = pyupbit.get_ohlcv(market, interval=interval, count=50)
            if df is not None:
                print(f"Success: {market} {interval} - {len(df)} rows")
            else:
                print(f"Failed: {market} {interval} - None returned")
        except Exception as e:
            print(f"Error: {market} {interval} - {e}")
        time.sleep(0.1)
