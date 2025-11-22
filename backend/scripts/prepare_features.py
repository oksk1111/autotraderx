"""
특성 엔지니어링 스크립트
수집한 데이터에서 기술적 지표를 계산하고 ML 학습용 데이터셋을 생성합니다.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple
import sys

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from app.services.indicators.technical import TechnicalIndicators
except ImportError:
    # Docker 외부에서 실행할 때를 위한 대체 구현
    class TechnicalIndicators:
        @staticmethod
        def calculate_rsi(prices, period=14):
            import pandas as pd
            delta = pd.Series(prices).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50).values  # NaN을 중립값 50으로 채움
        
        @staticmethod
        def calculate_macd(prices, fast=12, slow=26, signal=9):
            import pandas as pd
            prices_series = pd.Series(prices)
            ema_fast = prices_series.ewm(span=fast).mean()
            ema_slow = prices_series.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal).mean()
            histogram = macd - signal_line
            return {
                'macd': macd.values,
                'signal': signal_line.values,
                'histogram': histogram.values
            }
        
        @staticmethod
        def calculate_bollinger_bands(prices, period=20, std_dev=2):
            import pandas as pd
            prices_series = pd.Series(prices)
            middle = prices_series.rolling(window=period).mean()
            std = prices_series.rolling(window=period).std()
            upper = middle + (std * std_dev)
            lower = middle - (std * std_dev)
            bandwidth = (upper - lower) / middle
            return {
                'upper': upper.values,
                'middle': middle.values,
                'lower': lower.values,
                'bandwidth': bandwidth.values
            }
        
        @staticmethod
        def calculate_atr(high, low, close, period=14):
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)
            
            tr1 = high_series - low_series
            tr2 = abs(high_series - close_series.shift())
            tr3 = abs(low_series - close_series.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            return atr.values

# 디렉토리 설정 - 절대 경로 사용 (Docker 컨테이너 호환)
DATA_DIR = Path("/app/data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    기술적 지표를 계산하여 특성 추가
    """
    print("Calculating technical indicators...")
    
    # 복사본 생성
    features_df = df.copy()
    
    # 가격 변화율
    features_df['returns'] = features_df['close'].pct_change()
    features_df['log_returns'] = np.log(features_df['close'] / features_df['close'].shift(1))
    
    # 가격 관련
    features_df['high_low_ratio'] = features_df['high'] / features_df['low']
    features_df['close_open_ratio'] = features_df['close'] / features_df['open']
    
    # 거래량 관련
    features_df['volume_change'] = features_df['volume'].pct_change()
    features_df['volume_ma_ratio'] = features_df['volume'] / features_df['volume'].rolling(20).mean()
    
    # RSI
    rsi_values = TechnicalIndicators.calculate_rsi(
        features_df['close'].values,
        period=14
    )
    features_df['rsi'] = rsi_values
    
    # MACD
    macd_data = TechnicalIndicators.calculate_macd(
        features_df['close'].values,
        fast=12, slow=26, signal=9
    )
    features_df['macd'] = macd_data['macd']
    features_df['macd_signal'] = macd_data['signal']
    features_df['macd_hist'] = macd_data['histogram']
    
    # Bollinger Bands
    bb_data = TechnicalIndicators.calculate_bollinger_bands(
        features_df['close'].values,
        period=20, std_dev=2
    )
    features_df['bb_upper'] = bb_data['upper']
    features_df['bb_middle'] = bb_data['middle']
    features_df['bb_lower'] = bb_data['lower']
    features_df['bb_width'] = bb_data['bandwidth']
    features_df['bb_position'] = (features_df['close'] - features_df['bb_lower']) / (features_df['bb_upper'] - features_df['bb_lower'])
    
    # ATR (Average True Range)
    atr_values = TechnicalIndicators.calculate_atr(
        features_df['high'].values,
        features_df['low'].values,
        features_df['close'].values,
        period=14
    )
    features_df['atr'] = atr_values
    features_df['atr_ratio'] = features_df['atr'] / features_df['close']
    
    # 이동평균
    for period in [5, 10, 20, 50, 100]:
        features_df[f'sma_{period}'] = features_df['close'].rolling(period).mean()
        features_df[f'ema_{period}'] = features_df['close'].ewm(span=period).mean()
        features_df[f'price_to_sma_{period}'] = features_df['close'] / features_df[f'sma_{period}']
    
    # 변동성
    features_df['volatility_5'] = features_df['returns'].rolling(5).std()
    features_df['volatility_20'] = features_df['returns'].rolling(20).std()
    
    # 모멘텀
    for period in [5, 10, 20]:
        features_df[f'momentum_{period}'] = features_df['close'] - features_df['close'].shift(period)
        features_df[f'roc_{period}'] = features_df['close'].pct_change(period)
    
    print(f"Added {len(features_df.columns) - len(df.columns)} new features")
    return features_df


def create_labels(df: pd.DataFrame, horizon: int = 24) -> pd.DataFrame:
    """
    레이블 생성: 미래 수익률을 기반으로 매수/매도/보류 레이블 생성
    
    Args:
        df: 특성이 추가된 데이터프레임
        horizon: 예측 시간 (시간 단위)
    """
    print(f"Creating labels with {horizon}h horizon...")
    
    labeled_df = df.copy()
    
    # 미래 수익률 계산
    labeled_df['future_return'] = labeled_df['close'].shift(-horizon) / labeled_df['close'] - 1
    
    # 레이블 생성 (3-class classification)
    # 상승 > 1%, 하락 < -1%, 그 외 보류
    labeled_df['label'] = 0  # 보류
    labeled_df.loc[labeled_df['future_return'] > 0.01, 'label'] = 1  # 매수
    labeled_df.loc[labeled_df['future_return'] < -0.01, 'label'] = -1  # 매도
    
    # 긴급 상황 레이블 (급격한 하락)
    labeled_df['emergency'] = (labeled_df['future_return'] < -0.03).astype(int)
    
    print(f"Label distribution:")
    print(labeled_df['label'].value_counts())
    print(f"Emergency cases: {labeled_df['emergency'].sum()}")
    
    return labeled_df


def prepare_sequences(df: pd.DataFrame, sequence_length: int = 24, batch_size: int = 5000) -> Tuple[np.ndarray, np.ndarray, list]:
    """
    LSTM 학습을 위한 시퀀스 데이터 생성 (메모리 효율적인 배치 처리)
    
    Args:
        df: 특성과 레이블이 있는 데이터프레임
        sequence_length: 시퀀스 길이 (시간 단위)
        batch_size: 한 번에 처리할 시퀀스 개수
    """
    print(f"Creating sequences (length: {sequence_length}) with batch processing...")
    
    # NaN 처리: forward fill -> backward fill -> 남은 NaN은 0으로 채움
    df_clean = df.copy()
    df_clean = df_clean.ffill().bfill().fillna(0)
    
    # 특성 컬럼 선택 (레이블 제외)
    feature_cols = [col for col in df_clean.columns 
                   if col not in ['label', 'future_return', 'emergency']]
    
    num_sequences = len(df_clean) - sequence_length
    num_features = len(feature_cols)
    
    # 미리 배열 할당 (메모리 효율)
    X = np.zeros((num_sequences, sequence_length, num_features), dtype=np.float32)
    y = np.zeros(num_sequences, dtype=np.int8)
    
    # 배치 단위로 처리
    features_array = df_clean[feature_cols].values.astype(np.float32)
    labels_array = df_clean['label'].values.astype(np.int8)
    
    for i in range(0, num_sequences, batch_size):
        end_idx = min(i + batch_size, num_sequences)
        
        for j in range(i, end_idx):
            X[j] = features_array[j:j+sequence_length]
            y[j] = labels_array[j+sequence_length]
        
        if (i // batch_size) % 5 == 0:  # 5배치마다 진행상황 출력
            progress = (end_idx / num_sequences) * 100
            print(f"  Progress: {progress:.1f}% ({end_idx}/{num_sequences})")
    
    print(f"Created {len(X)} sequences")
    print(f"Shape: X={X.shape}, y={y.shape}")
    print(f"Memory usage: X={X.nbytes / 1024 / 1024:.1f} MB, y={y.nbytes / 1024:.1f} MB")
    
    return X, y, feature_cols


def process_market_data(market: str, interval: str = "minute60"):
    """
    특정 마켓의 데이터 처리
    """
    print("=" * 60)
    print(f"Processing {market} ({interval})")
    print("=" * 60)
    
    # 원본 데이터 로드
    filename = f"{market.replace('-', '_')}_{interval}.csv"
    filepath = RAW_DIR / filename
    
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return
    
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    print(f"Loaded {len(df)} rows")
    
    # 특성 계산
    features_df = calculate_features(df)
    
    # 레이블 생성
    labeled_df = create_labels(features_df, horizon=24)
    
    # 저장
    output_file = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_processed.csv"
    labeled_df.to_csv(output_file)
    print(f"Saved to {output_file}")
    
    # Parquet 형식으로도 저장 (더 효율적) - pyarrow가 있을 경우만
    try:
        output_parquet = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_processed.parquet"
        labeled_df.to_parquet(output_parquet)
        print(f"Saved to {output_parquet}")
    except ImportError:
        print("Skipping parquet format (pyarrow not installed)")
    
    # 시퀀스 데이터 생성 및 저장
    X, y, feature_cols = prepare_sequences(labeled_df, sequence_length=24)
    
    sequence_file = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_sequences.npz"
    np.savez_compressed(
        sequence_file,
        X=X,
        y=y,
        feature_names=feature_cols
    )
    print(f"Saved sequences to {sequence_file}")
    print()


def main():
    """
    메인 실행 함수
    """
    markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]
    
    print("Starting feature engineering...")
    print(f"Raw data directory: {RAW_DIR}")
    print(f"Processed data directory: {PROCESSED_DIR}")
    print()
    
    for market in markets:
        try:
            process_market_data(market, interval="minute60")
        except Exception as e:
            print(f"Error processing {market}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("=" * 60)
    print("Feature engineering completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
