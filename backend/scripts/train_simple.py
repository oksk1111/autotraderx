"""
간단한 ML 모델 학습 (LightGBM만 사용)
"""
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
import json
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
import lightgbm as lgb

# 디렉토리 설정
DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def create_tabular_features(df, lookback=24):
    """
    시계열 데이터를 테이블 형식으로 변환 (LSTM 없이)
    """
    print(f"Creating tabular features with lookback={lookback}...")
    
    # 특성 컬럼 선택
    feature_cols = [col for col in df.columns 
                   if col not in ['label', 'future_return', 'emergency']]
    
    X_list = []
    y_list = []
    
    for i in range(lookback, len(df)):
        # 과거 lookback 기간의 통계 정보 사용
        window = df[feature_cols].iloc[i-lookback:i]
        
        # 현재 값
        current = df[feature_cols].iloc[i].values
        
        # 통계량
        mean_vals = window.mean().values
        std_vals = window.std().values
        min_vals = window.min().values
        max_vals = window.max().values
        
        # 변화율
        if i > lookback:
            prev = df[feature_cols].iloc[i-1].values
            change = (current - prev) / (prev + 1e-8)
        else:
            change = np.zeros_like(current)
        
        # 모든 특성 결합
        features = np.concatenate([current, mean_vals, std_vals, min_vals, max_vals, change])
        
        X_list.append(features)
        y_list.append(df['label'].iloc[i])
    
    X = np.array(X_list)
    y = np.array(y_list)
    
    print(f"Created {len(X)} samples with {X.shape[1]} features")
    return X, y


def train_lightgbm_model(market="KRW-BTC", interval="1h"):
    """
    LightGBM 모델 학습
    """
    print("="*60)
    print(f"Training LightGBM Model for {market}")
    print("="*60)
    
    # 데이터 로드
    data_file = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_processed.csv"
    
    if not data_file.exists():
        print(f"Data file not found: {data_file}")
        return
    
    df = pd.read_csv(data_file, index_col=0, parse_dates=True)
    df = df.dropna()
    
    print(f"Loaded {len(df)} rows")
    print(f"Label distribution:\n{df['label'].value_counts()}")
    
    # 특성 생성
    X, y = create_tabular_features(df, lookback=24)
    
    # 레이블을 0, 1, 2로 변환 (-1, 0, 1 -> 0, 1, 2)
    y_shifted = y + 1
    
    # 데이터 분할
    X_temp, X_test, y_temp, y_test = train_test_split(X, y_shifted, test_size=0.15, random_state=42, stratify=y_shifted)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.18, random_state=42, stratify=y_temp)
    
    print(f"\nData split:")
    print(f"  Train: {len(X_train)}")
    print(f"  Val: {len(X_val)}")
    print(f"  Test: {len(X_test)}")
    
    # 데이터 정규화
    print("\nNormalizing data...")
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)
    
    # Scaler 저장
    with open(MODEL_DIR / "scaler.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    print("Saved scaler")
    
    # LightGBM 데이터셋 생성
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
    
    # 파라미터 설정
    params = {
        'objective': 'multiclass',
        'num_class': 3,
        'metric': 'multi_logloss',
        'boosting_type': 'gbdt',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': 6,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1
    }
    
    print("\nTraining LightGBM model...")
    model = lgb.train(
        params,
        train_data,
        num_boost_round=200,
        valid_sets=[train_data, val_data],
        valid_names=['train', 'valid'],
        callbacks=[
            lgb.early_stopping(stopping_rounds=20),
            lgb.log_evaluation(period=10)
        ]
    )
    
    # 모델 저장
    model.save_model(str(MODEL_DIR / "lightgbm_model.txt"))
    print(f"Model saved to {MODEL_DIR / 'lightgbm_model.txt'}")
    
    # 평가
    print("\n" + "="*60)
    print("Model Evaluation")
    print("="*60)
    
    y_pred_proba = model.predict(X_test)
    y_pred = np.argmax(y_pred_proba, axis=1)
    
    # 레이블을 원래대로 변환 (0, 1, 2 -> -1, 0, 1)
    y_test_original = y_test - 1
    y_pred_original = y_pred - 1
    
    print("\nClassification Report:")
    print(classification_report(y_test_original, y_pred_original, 
                                target_names=['Sell', 'Hold', 'Buy']))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test_original, y_pred_original)
    print(cm)
    
    # 클래스별 정확도
    print("\nClass-wise accuracy:")
    for label, name in [(-1, 'Sell'), (0, 'Hold'), (1, 'Buy')]:
        mask = y_test_original == label
        if mask.sum() > 0:
            accuracy = (y_pred_original[mask] == label).sum() / mask.sum()
            print(f"  {name}: {accuracy:.2%} ({mask.sum()} samples)")
    
    # 전체 정확도
    accuracy = (y_pred_original == y_test_original).sum() / len(y_test_original)
    print(f"\nOverall accuracy: {accuracy:.2%}")
    
    # Feature importance 상위 20개
    print("\nTop 20 important features:")
    importance = model.feature_importance(importance_type='gain')
    indices = np.argsort(importance)[::-1][:20]
    for i, idx in enumerate(indices, 1):
        print(f"  {i}. Feature {idx}: {importance[idx]:.2f}")
    
    # 메타데이터 저장
    metadata = {
        'market': market,
        'interval': interval,
        'model_type': 'lightgbm_only',
        'trained_at': datetime.now().isoformat(),
        'n_features': X_train.shape[1],
        'lookback': 24,
        'train_size': len(X_train),
        'val_size': len(X_val),
        'test_size': len(X_test),
        'test_accuracy': float(accuracy),
        'class_distribution': {
            'sell': int((y_test_original == -1).sum()),
            'hold': int((y_test_original == 0).sum()),
            'buy': int((y_test_original == 1).sum())
        }
    }
    
    with open(MODEL_DIR / "model_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"\nMetadata saved to {MODEL_DIR / 'model_metadata.json'}")
    
    print(f"\n✅ Training completed!")
    print(f"Models saved to: {MODEL_DIR}")
    
    return model, scaler, metadata


if __name__ == "__main__":
    train_lightgbm_model(market="KRW-BTC", interval="minute60")
