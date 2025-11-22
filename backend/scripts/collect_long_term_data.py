"""
장기 데이터 수집 스크립트 (1-2년)
pyupbit API 제약을 고려한 대량 데이터 수집
"""
import pyupbit
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import time
import sys

# Docker 경로
DATA_DIR = Path("/app/data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 수집할 마켓
MARKETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]

def collect_historical_data(market: str, days: int = 730):
    """
    과거 데이터 대량 수집 (최대 2년)
    
    Args:
        market: 마켓 코드 (예: "KRW-BTC")
        days: 수집 기간 (일 단위, 기본 730일 = 2년)
    
    Note:
        pyupbit.get_ohlcv()는 최대 200개 캔들만 반환
        1시간봉 기준: 200시간 = 약 8.3일
        2년 = 730일 = 17,520시간 → 88번 API 호출 필요
    """
    print(f"\n{'='*60}")
    print(f"Collecting {days} days of data for {market}")
    print(f"{'='*60}\n")
    
    all_data = []
    target_hours = days * 24
    iterations = (target_hours // 200) + 1
    
    print(f"Target: {target_hours} hours ({days} days)")
    print(f"API calls needed: {iterations}")
    print()
    
    end_date = datetime.now()
    
    for i in range(iterations):
        try:
            # 종료 시점 계산
            to_date = end_date - timedelta(hours=200 * i)
            
            # 데이터 가져오기
            df = pyupbit.get_ohlcv(
                market,
                interval="minute60",
                count=200,
                to=to_date.strftime("%Y%m%d%H%M%S")
            )
            
            if df is not None and len(df) > 0:
                all_data.append(df)
                collected = len(all_data) * 200
                progress = (collected / target_hours) * 100
                
                print(f"[{i+1}/{iterations}] Collected {len(df)} candles "
                      f"(Total: {collected}/{target_hours}, {progress:.1f}%)")
                
                # Rate limiting: pyupbit는 초당 10회 제한
                time.sleep(0.12)
            else:
                print(f"[{i+1}/{iterations}] No data returned")
                break
                
        except Exception as e:
            print(f"[{i+1}/{iterations}] Error: {e}")
            time.sleep(1)
            continue
    
    if not all_data:
        print(f"❌ No data collected for {market}")
        return None
    
    # 데이터 합치기
    print(f"\n📊 Merging {len(all_data)} chunks...")
    combined = pd.concat(all_data, axis=0)
    
    # 중복 제거 (인덱스 기준)
    combined = combined[~combined.index.duplicated(keep='first')]
    
    # 시간순 정렬
    combined = combined.sort_index()
    
    # 저장
    output_file = DATA_DIR / f"{market.replace('-', '_')}_minute60.csv"
    combined.to_csv(output_file)
    
    print(f"\n✅ Collection complete!")
    print(f"   Total rows: {len(combined)}")
    print(f"   Period: {len(combined) / 24:.0f} days ({len(combined) / 24 / 30:.1f} months)")
    print(f"   Start: {combined.index[0]}")
    print(f"   End: {combined.index[-1]}")
    print(f"   Saved to: {output_file}")
    print(f"   File size: {output_file.stat().st_size / 1024:.0f} KB")
    
    return combined


def main():
    """모든 마켓에 대해 데이터 수집"""
    
    # 수집 기간 설정
    if len(sys.argv) > 1:
        days = int(sys.argv[1])
    else:
        days = 730  # 기본 2년
    
    print(f"🚀 Starting historical data collection")
    print(f"   Markets: {', '.join(MARKETS)}")
    print(f"   Period: {days} days ({days / 365:.1f} years)")
    print(f"   Interval: 1 hour (minute60)")
    print()
    
    results = {}
    
    for market in MARKETS:
        try:
            df = collect_historical_data(market, days)
            if df is not None:
                results[market] = len(df)
            time.sleep(0.5)  # 마켓 간 여유
        except Exception as e:
            print(f"❌ Failed to collect {market}: {e}")
            continue
    
    # 요약
    print(f"\n{'='*60}")
    print(f"Collection Summary")
    print(f"{'='*60}")
    for market, rows in results.items():
        print(f"  {market}: {rows} rows ({rows / 24:.0f} days)")
    print(f"\nTotal: {sum(results.values())} rows")
    print(f"Ready for feature engineering: python3 /app/prepare_features.py")


if __name__ == "__main__":
    main()
