"""
시퀀스 데이터 생성 (LSTM 입력용)
"""
import pandas as pd
import numpy as np
from pathlib import Path

# 디렉토리 설정
DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"

def create_sequences(market="KRW-BTC", interval="1h", sequence_length=24):
    """
    처리된 데이터에서 시퀀스 생성
    """
    print(f"Creating sequences for {market}...")
    
    # 처리된 데이터 로드
    filepath = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_processed.csv"
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    
    print(f"Loaded {len(df)} rows with {len(df.columns)} columns")
    
    # NaN 제거
    df_clean = df.dropna()
    print(f"After removing NaN: {len(df_clean)} rows")
    
    # 특성 컬럼 선택 (레이블 제외)
    feature_cols = [col for col in df_clean.columns 
                   if col not in ['label', 'future_return', 'emergency']]
    
    print(f"Using {len(feature_cols)} features")
    
    X_list = []
    y_list = []
    
    for i in range(len(df_clean) - sequence_length):
        # 시퀀스 추출
        sequence = df_clean[feature_cols].iloc[i:i+sequence_length].values
        label = df_clean['label'].iloc[i+sequence_length]
        
        X_list.append(sequence)
        y_list.append(label)
    
    X = np.array(X_list)
    y = np.array(y_list)
    
    print(f"Created {len(X)} sequences")
    print(f"Shape: X={X.shape}, y={y.shape}")
    
    # 저장
    output_file = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_sequences.npz"
    np.savez_compressed(
        output_file,
        X=X,
        y=y,
        feature_names=np.array(feature_cols)
    )
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    create_sequences()
    print("\n✅ Sequence creation completed!")
