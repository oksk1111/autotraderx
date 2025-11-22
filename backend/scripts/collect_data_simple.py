"""간단한 데이터 수집 스크립트 (Docker 내부용)"""
import pyupbit
import pandas as pd
from pathlib import Path
import time

DATA_DIR = Path('/app/data/raw')
DATA_DIR.mkdir(parents=True, exist_ok=True)

MARKETS = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL']

def collect_market(market, interval='minute60', count=2000):
    print('\n' + '='*60)
    print(f'Collecting {market} ({interval})')
    print('='*60)
    
    all_data = []
    remaining = count
    to_time = None
    
    while remaining > 0:
        batch_size = min(200, remaining)
        
        try:
            df = pyupbit.get_ohlcv(market, interval=interval, count=batch_size, to=to_time)
            
            if df is None or df.empty:
                print('  No more data')
                break
            
            all_data.append(df)
            remaining -= len(df)
            to_time = df.index[0]
            
            total_so_far = sum(len(d) for d in all_data)
            print(f'  Batch: {len(df)} rows, Total: {total_so_far}, Remaining: {remaining}')
            
            if len(df) < batch_size:
                break
            
            time.sleep(0.1)
        except Exception as e:
            print(f'  Error: {e}')
            break
    
    if not all_data:
        return None
    
    final_df = pd.concat(all_data)
    final_df = final_df.sort_index()
    final_df = final_df[~final_df.index.duplicated(keep='first')]
    
    filename = f"{market.replace('-', '_')}_{interval}.csv"
    filepath = DATA_DIR / filename
    final_df.to_csv(filepath)
    
    print(f'  ✅ Saved {len(final_df)} rows to {filepath}')
    print(f'  Date range: {final_df.index[0]} to {final_df.index[-1]}')
    return final_df

if __name__ == '__main__':
    for market in MARKETS:
        collect_market(market, 'minute60', 2000)
        time.sleep(1)
    
    print('\n' + '='*60)
    print('All data collected!')
    print('='*60)
