"""
GPU 가속 ML 모델 학습 스크립트
LSTM + LightGBM 하이브리드 모델 학습 (CUDA 지원)
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
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import sys

# 디렉토리 설정 - Docker 컨테이너 호환
DATA_DIR = Path("/app/data")
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = Path("/app/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class LSTMModel(nn.Module):
    """
    LSTM 기반 시계열 예측 모델 (대용량 데이터 최적화)
    """
    def __init__(self, input_size: int, hidden_size: int = 256, num_layers: int = 3, dropout: float = 0.4):
        super(LSTMModel, self).__init__()
        
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(hidden_size, 128)
        self.relu = nn.ReLU()
        self.ln1 = nn.LayerNorm(128)
        self.fc2 = nn.Linear(128, 64)
        
    def forward(self, x):
        # LSTM
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # 마지막 타임스텝의 출력 사용
        last_output = lstm_out[:, -1, :]
        
        # Fully connected layers with layer normalization
        out = self.dropout(last_output)
        out = self.fc1(out)
        out = self.ln1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        
        return out


class TimeSeriesDataset(Dataset):
    """
    PyTorch Dataset for time series
    """
    def __init__(self, X, y):
        self.X = torch.FloatTensor(X)
        self.y = torch.LongTensor(y)
    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


def train_lstm(X_train, y_train, X_val, y_val, input_size, device, epochs=100, batch_size=64):
    """
    LSTM 모델 학습 (GPU 지원, 대용량 데이터 최적화)
    """
    print(f"Training LSTM model on {device}...")
    
    # 레이블을 0, 1, 2로 변환 (-1, 0, 1 -> 0, 1, 2)
    y_train_shifted = y_train + 1
    y_val_shifted = y_val + 1
    
    # 데이터셋 생성
    train_dataset = TimeSeriesDataset(X_train, y_train_shifted)
    val_dataset = TimeSeriesDataset(X_val, y_val_shifted)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # 모델 초기화 (더 큰 모델)
    model = LSTMModel(input_size=input_size, hidden_size=256, num_layers=3, dropout=0.4)
    model = model.to(device)
    
    # 손실 함수와 옵티마이저
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0005, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=7, verbose=True, min_lr=1e-6
    )
    
    # 학습
    best_val_loss = float('inf')
    patience_counter = 0
    patience_limit = 15
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # Validation
        model.eval()
        val_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()
                
                _, predicted = torch.max(outputs.data, 1)
                total += batch_y.size(0)
                correct += (predicted == batch_y).sum().item()
        
        val_loss /= len(val_loader)
        val_accuracy = 100 * correct / total
        
        # Learning rate scheduling
        scheduler.step(val_loss)
        
        # 진행 상황 출력
        if (epoch + 1) % 5 == 0:
            print(f"Epoch [{epoch+1}/{epochs}] - Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}, Val Acc: {val_accuracy:.2f}%")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # 최상의 모델 저장
            torch.save(model.state_dict(), MODEL_DIR / "lstm_best.pth")
        else:
            patience_counter += 1
            if patience_counter >= patience_limit:
                print(f"Early stopping at epoch {epoch+1}")
                break
    
    # 최상의 모델 로드
    model.load_state_dict(torch.load(MODEL_DIR / "lstm_best.pth"))
    print(f"Best validation loss: {best_val_loss:.4f}")
    
    return model


def extract_lstm_features(model, X, device, batch_size=32):
    """
    LSTM 모델에서 특성 추출
    """
    model.eval()
    features_list = []
    
    dataset = torch.utils.data.TensorDataset(torch.FloatTensor(X))
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    
    with torch.no_grad():
        for batch in loader:
            batch_X = batch[0].to(device)
            features = model(batch_X)
            features_list.append(features.cpu().numpy())
    
    return np.vstack(features_list)


def train_hybrid_model(market="KRW-BTC", interval="minute60"):
    """
    하이브리드 모델 학습 (LSTM + LightGBM)
    """
    print("="*60)
    print(f"Training Hybrid Model for {market}")
    print("="*60)
    
    # GPU 체크
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    if device.type == 'cuda':
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    # 시퀀스 데이터 로드
    sequence_file = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_sequences.npz"
    
    if not sequence_file.exists():
        print(f"Sequence file not found: {sequence_file}")
        return
    
    data = np.load(sequence_file, allow_pickle=True)
    X = data['X']
    y = data['y']
    feature_names = data['feature_names']
    
    print(f"Loaded sequences: X.shape={X.shape}, y.shape={y.shape}")
    print(f"Number of features: {len(feature_names)}")
    print(f"Label distribution: {np.bincount(y + 1)}")  # -1, 0, 1 -> 0, 1, 2
    
    # 데이터 분할
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.18, random_state=42, stratify=y_temp)
    
    print(f"\nData split:")
    print(f"  Train: {len(X_train)}")
    print(f"  Val: {len(X_val)}")
    print(f"  Test: {len(X_test)}")
    
    # 데이터 정규화 (각 특성별로)
    print("\nNormalizing data...")
    n_timesteps, n_features = X_train.shape[1], X_train.shape[2]
    
    # 시퀀스 데이터를 2D로 변환하여 정규화
    X_train_2d = X_train.reshape(-1, n_features)
    X_val_2d = X_val.reshape(-1, n_features)
    X_test_2d = X_test.reshape(-1, n_features)
    
    scaler = StandardScaler()
    X_train_2d = scaler.fit_transform(X_train_2d)
    X_val_2d = scaler.transform(X_val_2d)
    X_test_2d = scaler.transform(X_test_2d)
    
    # 다시 3D로 변환
    X_train = X_train_2d.reshape(-1, n_timesteps, n_features)
    X_val = X_val_2d.reshape(-1, n_timesteps, n_features)
    X_test = X_test_2d.reshape(-1, n_timesteps, n_features)
    
    # Scaler 저장
    with open(MODEL_DIR / "scaler.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    print("Saved scaler")
    
    # ===== Phase 1: LSTM 학습 =====
    print("\n" + "="*60)
    print("Phase 1: Training LSTM")
    print("="*60)
    
    lstm_model = train_lstm(
        X_train, y_train, 
        X_val, y_val, 
        input_size=n_features,
        device=device,
        epochs=100,
        batch_size=64
    )
    
    print(f"LSTM model saved to {MODEL_DIR / 'lstm_best.pth'}")
    
    # ===== Phase 2: LSTM 특성 추출 =====
    print("\n" + "="*60)
    print("Phase 2: Extracting LSTM features")
    print("="*60)
    
    lstm_train_features = extract_lstm_features(lstm_model, X_train, device)
    lstm_val_features = extract_lstm_features(lstm_model, X_val, device)
    lstm_test_features = extract_lstm_features(lstm_model, X_test, device)
    
    print(f"LSTM features shape: {lstm_train_features.shape}")
    
    # ===== Phase 3: LightGBM 학습 =====
    print("\n" + "="*60)
    print("Phase 3: Training LightGBM on LSTM features")
    print("="*60)
    
    # 레이블을 0, 1, 2로 변환
    y_train_shifted = y_train + 1
    y_val_shifted = y_val + 1
    y_test_shifted = y_test + 1
    
    # LightGBM 데이터셋 생성
    train_data = lgb.Dataset(lstm_train_features, label=y_train_shifted)
    val_data = lgb.Dataset(lstm_val_features, label=y_val_shifted, reference=train_data)
    
    # 파라미터 설정 (대용량 데이터 최적화)
    params = {
        'objective': 'multiclass',
        'num_class': 3,
        'metric': 'multi_logloss',
        'boosting_type': 'gbdt',
        'device': 'gpu' if device.type == 'cuda' else 'cpu',
        'gpu_platform_id': 0,
        'gpu_device_id': 0,
        'learning_rate': 0.03,
        'num_leaves': 63,
        'max_depth': 8,
        'min_data_in_leaf': 50,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.9,
        'bagging_freq': 5,
        'lambda_l1': 0.1,
        'lambda_l2': 0.1,
        'verbose': -1
    }
    
    print(f"Training LightGBM on {params['device']}...")
    lgb_model = lgb.train(
        params,
        train_data,
        num_boost_round=300,
        valid_sets=[train_data, val_data],
        valid_names=['train', 'valid'],
        callbacks=[
            lgb.early_stopping(stopping_rounds=30),
            lgb.log_evaluation(period=10)
        ]
    )
    
    # 모델 저장
    lgb_model.save_model(str(MODEL_DIR / "lightgbm_model.txt"))
    print(f"LightGBM model saved to {MODEL_DIR / 'lightgbm_model.txt'}")
    
    # ===== Phase 4: 평가 =====
    print("\n" + "="*60)
    print("Phase 4: Model Evaluation")
    print("="*60)
    
    # 테스트 예측
    y_pred_proba = lgb_model.predict(lstm_test_features)
    y_pred = np.argmax(y_pred_proba, axis=1)
    
    # 레이블을 원래대로 변환 (0, 1, 2 -> -1, 0, 1)
    y_test_original = y_test_shifted - 1
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
    
    # Feature importance
    print("\nLSTM feature importance (from LightGBM):")
    importance = lgb_model.feature_importance(importance_type='gain')
    for i, imp in enumerate(importance, 1):
        print(f"  LSTM feature {i}: {imp:.2f}")
    
    # 메타데이터 저장
    metadata = {
        'market': market,
        'interval': interval,
        'model_type': 'lstm_lightgbm_hybrid',
        'device': str(device),
        'trained_at': datetime.now().isoformat(),
        'lstm_config': {
            'input_size': n_features,
            'hidden_size': 256,
            'num_layers': 3,
            'dropout': 0.4,
            'epochs': 100,
            'batch_size': 64
        },
        'sequence_length': n_timesteps,
        'n_features': n_features,
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
    
    return lstm_model, lgb_model, scaler, metadata


def train_all_markets():
    """
    모든 마켓에 대해 학습 수행
    """
    markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]
    
    for market in markets:
        try:
            print(f"\n{'='*60}")
            print(f"Training model for {market}")
            print(f"{'='*60}\n")
            
            train_hybrid_model(market=market, interval="minute60")
            
        except Exception as e:
            print(f"❌ Error training {market}: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        # 모든 마켓 학습
        train_all_markets()
    else:
        # 단일 마켓 학습 (기본: BTC)
        market = sys.argv[1] if len(sys.argv) > 1 else "KRW-BTC"
        train_hybrid_model(market=market, interval="minute60")
