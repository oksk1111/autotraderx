"""
데이터 수집 스크립트
Upbit API를 사용하여 과거 시장 데이터를 수집합니다.
"""
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path

# 데이터 저장 디렉토리
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 수집할 마켓 목록
MARKETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]

# 수집할 기간 설정
DAYS_TO_COLLECT = 365  # 1년치 데이터


def collect_ohlcv_data(market: str, interval: str = "minute60", count: int = 8760):
    """
    OHLCV(시가, 고가, 저가, 종가, 거래량) 데이터 수집
    
    Args:
        market: 마켓 코드 (예: KRW-BTC)
        interval: 시간 간격 (minute1, minute60, day)
        count: 수집할 데이터 개수 (최대 200개씩 분할 요청)
    """
    print(f"Collecting {market} data (interval: {interval}, count: {count})...")
    
    all_data = []
    remaining = count
    to_time = None
    
    while remaining > 0:
        batch_size = min(200, remaining)  # Upbit API는 한 번에 최대 200개
        
        try:
            df = pyupbit.get_ohlcv(market, interval=interval, count=batch_size, to=to_time)
            
            if df is None or df.empty:
                print(f"  No more data available for {market}")
                break
                
            all_data.append(df)
            remaining -= len(df)
            
            # 다음 배치를 위해 마지막 시간 설정 (가장 오래된 시간)
            to_time = df.index[0]
            
            print(f"  Collected {len(df)} rows. Total so far: {sum(len(d) for d in all_data)}, Remaining: {remaining}")
            
            if len(df) < batch_size:
                # 더 이상 데이터가 없음
                print(f"  Received less than requested ({len(df)} < {batch_size}), stopping")
                break
            
            # API 레이트 리밋 방지
            import time
            time.sleep(0.1)
                
        except Exception as e:
            print(f"  Error collecting data for {market}: {e}")
            break
    
    if not all_data:
        print(f"  ❌ No data collected for {market}")
        return None
    
    # 모든 배치 합치기
    final_df = pd.concat(all_data)
    final_df = final_df.sort_index()
    final_df = final_df[~final_df.index.duplicated(keep='first')]  # 중복 제거
    
    print(f"  ✅ Total collected: {len(final_df)} rows for {market}")
    return final_df


def collect_orderbook_snapshot(market: str):
    """
    현재 호가 정보 수집 (실시간 스냅샷)
    """
    try:
        orderbook = pyupbit.get_orderbook(market)
        if orderbook:
            return {
                'timestamp': datetime.now(),
                'market': market,
                'orderbook_units': orderbook[0]['orderbook_units']
            }
    except Exception as e:
        print(f"Error collecting orderbook for {market}: {e}")
    return None


def save_data(df: pd.DataFrame, market: str, interval: str):
    """
    데이터를 CSV 파일로 저장
    """
    filename = f"{market.replace('-', '_')}_{interval}.csv"
    filepath = DATA_DIR / filename
    
    df.to_csv(filepath)
    print(f"Saved to {filepath}")
    
    # 데이터 통계 출력
    print(f"Data range: {df.index[0]} to {df.index[-1]}")
    print(f"Total rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print()


def main():
    """
    메인 실행 함수
    """
    print("=" * 60)
    print("Starting data collection...")
    print(f"Markets: {MARKETS}")
    print(f"Data directory: {DATA_DIR}")
    print("=" * 60)
    print()
    
    for market in MARKETS:
        try:
            # 1시간 봉 데이터 수집 (1년치: 365*24 = 8760개)
            df_1h = collect_ohlcv_data(market, interval="minute60", count=8760)
            if df_1h is not None:
                save_data(df_1h, market, "1h")
            
            # 일봉 데이터 수집 (1년치: 365개)
            df_1d = collect_ohlcv_data(market, interval="day", count=365)
            if df_1d is not None:
                save_data(df_1d, market, "1d")
                
        except Exception as e:
            print(f"Failed to collect data for {market}: {e}")
            continue
    
    print("=" * 60)
    print("Data collection completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
