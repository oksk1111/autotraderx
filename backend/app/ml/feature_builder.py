"""
실시간 시장 데이터를 ML 입력 특징으로 변환
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    기술적 지표 계산 (train_gpu.py와 동일한 로직)
    
    Args:
        df: OHLCV 데이터프레임 (columns: open, high, low, close, volume, value)
    
    Returns:
        특징이 추가된 데이터프레임 (46개 특징)
    """
    df = df.copy()
    
    # 기본 특징
    df['returns'] = df['close'].pct_change()
    df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
    df['high_low_ratio'] = df['high'] / df['low']
    df['close_open_ratio'] = df['close'] / df['open']
    
    # 거래량 특징
    df['volume_change'] = df['volume'].pct_change()
    df['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
    
    # RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(50)
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']  # histogram
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # ATR (Average True Range)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close']
    
    # 이동평균
    for period in [5, 10, 20, 50, 100]:
        df[f'sma_{period}'] = df['close'].rolling(window=period).mean()
        df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        df[f'price_to_sma_{period}'] = df['close'] / df[f'sma_{period}']
    
    # 변동성
    df['volatility_5'] = df['returns'].rolling(window=5).std()
    df['volatility_20'] = df['returns'].rolling(window=20).std()
    
    # 모멘텀
    for period in [5, 10, 20]:
        df[f'momentum_{period}'] = df['close'] - df['close'].shift(period)
        df[f'roc_{period}'] = df['close'].pct_change(period)
    
    # NaN 처리
    df = df.ffill().bfill().fillna(0)
    
    return df


def prepare_sequence_for_prediction(df: pd.DataFrame, sequence_length: int = 24) -> np.ndarray:
    """
    최근 데이터를 LSTM 입력 시퀀스로 변환
    
    Args:
        df: 기술적 지표가 계산된 데이터프레임
        sequence_length: 시퀀스 길이 (기본 24시간)
    
    Returns:
        (sequence_length, n_features) 형태의 numpy 배열
    """
    # 특징 컬럼 목록 (학습 시와 정확히 동일한 순서 - 46개 특징)
    feature_columns = [
        'open', 'high', 'low', 'close', 'volume', 'value',
        'returns', 'log_returns', 'high_low_ratio', 'close_open_ratio',
        'volume_change', 'volume_ma_ratio',
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_position',
        'atr', 'atr_ratio',
        'sma_5', 'ema_5', 'price_to_sma_5',
        'sma_10', 'ema_10', 'price_to_sma_10',
        'sma_20', 'ema_20', 'price_to_sma_20',
        'sma_50', 'ema_50', 'price_to_sma_50',
        'sma_100', 'ema_100', 'price_to_sma_100',
        'volatility_5', 'volatility_20',
        'momentum_5', 'roc_5',
        'momentum_10', 'roc_10',
        'momentum_20', 'roc_20'
    ]
    
    # 최근 sequence_length개 행 추출
    if len(df) < sequence_length:
        raise ValueError(f"데이터 길이가 부족합니다. 필요: {sequence_length}, 현재: {len(df)}")
    
    recent_data = df.tail(sequence_length)
    
    # 특징 배열 생성
    sequence = recent_data[feature_columns].values
    
    return sequence


def build_features_from_market_data(market_data: List[Dict[str, Any]], market: str) -> Dict[str, Any]:
    """
    시장 데이터를 ML 입력 특징으로 변환
    
    Args:
        market_data: pyupbit 등에서 가져온 시장 데이터 리스트 (최소 150개 권장)
        market: 마켓 코드 (예: "KRW-BTC")
    
    Returns:
        {
            "market": market,
            "sequence": numpy array (24, 46)
        }
    """
    # DataFrame 생성
    df = pd.DataFrame(market_data)
    
    # 'index' 컬럼 제거 (pyupbit reset_index()에서 추가된 불필요한 컬럼)
    if 'index' in df.columns:
        df = df.drop(columns=['index'])
        logger.debug("Removed 'index' column from market data")
    
    # 필수 컬럼 확인
    required_columns = ['open', 'high', 'low', 'close', 'volume', 'value']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"필수 컬럼이 누락되었습니다: {required_columns}")
    
    # 기술적 지표 계산
    df = calculate_technical_indicators(df)
    
    # NaN 검증
    nan_count = df.isna().sum().sum()
    if nan_count > 0:
        logger.warning(f"NaN values detected in features for {market}: {nan_count} total")
        # NaN이 30% 이상이면 데이터 품질 문제로 간주
        total_cells = df.shape[0] * df.shape[1]
        if nan_count / total_cells > 0.3:
            raise ValueError(f"Too many NaN values in {market}: {nan_count}/{total_cells} ({nan_count/total_cells*100:.1f}%)")
    
    # 시퀀스 생성 (최근 24시간)
    sequence = prepare_sequence_for_prediction(df, sequence_length=24)
    
    return {
        "market": market,
        "sequence": sequence
    }
