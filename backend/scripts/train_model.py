"""
ML 모델 학습 스크립트
LSTM + LightGBM 하이브리드 모델 학습
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

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# 디렉토리 설정
DATA_DIR = Path(__file__).parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


class LSTMModel(nn.Module):
    """
    LSTM 기반 시계열 예측 모델
    """
    def __init__(self, input_size: int, hidden_size: int = 128, num_layers: int = 2, dropout: float = 0.3):
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
        self.fc1 = nn.Linear(hidden_size, 64)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(64, 32)
        
    def forward(self, x):
        # LSTM
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # 마지막 타임스텝의 출력 사용
        last_output = lstm_out[:, -1, :]
        
        # Fully connected layers
        out = self.dropout(last_output)
        out = self.fc1(out)
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


def train_lstm(X_train, y_train, X_val, y_val, input_size, epochs=50, batch_size=32):
    """
    LSTM 모델 학습
    """
    print("Training LSTM model...")
    
    # 레이블을 0, 1, 2로 변환 (-1, 0, 1 -> 0, 1, 2)
    y_train_shifted = y_train + 1
    y_val_shifted = y_val + 1
    
    # 데이터셋 생성
    train_dataset = TimeSeriesDataset(X_train, y_train_shifted)
    val_dataset = TimeSeriesDataset(X_val, y_val_shifted)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # 모델 초기화
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    model = LSTMModel(input_size=input_size).to(device)
    
    # 손실 함수 및 옵티마이저
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=5, factor=0.5)
    
    # 학습
    best_val_loss = float('inf')
    train_losses = []
    val_losses = []
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        train_losses.append(train_loss)
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        val_losses.append(val_loss)
        
        scheduler.step(val_loss)
        
        if (epoch + 1) % 5 == 0:
            print(f"Epoch [{epoch+1}/{epochs}], Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
        
        # 최고 모델 저장
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), MODEL_DIR / "lstm_best.pth")
    
    print(f"Best validation loss: {best_val_loss:.4f}")
    
    # 최고 모델 로드
    model.load_state_dict(torch.load(MODEL_DIR / "lstm_best.pth"))
    
    return model, device, train_losses, val_losses


def get_lstm_features(model, X, device, batch_size=32):
    """
    LSTM 모델에서 특성 추출 (LightGBM 입력용)
    """
    model.eval()
    features_list = []
    
    dataset = torch.FloatTensor(X)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    
    with torch.no_grad():
        for X_batch in loader:
            X_batch = X_batch.to(device)
            features = model(X_batch)
            features_list.append(features.cpu().numpy())
    
    return np.vstack(features_list)


def train_lightgbm(X_train, y_train, X_val, y_val):
    """
    LightGBM 모델 학습
    """
    print("Training LightGBM model...")
    
    # 레이블을 0, 1, 2로 변환
    y_train_shifted = y_train + 1
    y_val_shifted = y_val + 1
    
    # LightGBM 데이터셋 생성
    train_data = lgb.Dataset(X_train, label=y_train_shifted)
    val_data = lgb.Dataset(X_val, label=y_val_shifted, reference=train_data)
    
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
    
    # 학습
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
    
    return model


def evaluate_model(lstm_model, lgb_model, X_test, y_test, device):
    """
    모델 평가
    """
    print("\n" + "="*60)
    print("Model Evaluation")
    print("="*60)
    
    # LSTM 특성 추출
    lstm_features = get_lstm_features(lstm_model, X_test, device)
    
    # LightGBM 예측
    y_pred_proba = lgb_model.predict(lstm_features)
    y_pred = np.argmax(y_pred_proba, axis=1)
    
    # 레이블을 원래대로 변환 (0, 1, 2 -> -1, 0, 1)
    y_test_original = y_test
    y_pred_original = y_pred - 1
    
    # 평가
    print("\nClassification Report:")
    print(classification_report(y_test_original, y_pred_original, 
                                target_names=['Sell', 'Hold', 'Buy']))
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test_original, y_pred_original))
    
    # 클래스별 정확도
    for label, name in [(-1, 'Sell'), (0, 'Hold'), (1, 'Buy')]:
        mask = y_test_original == label
        if mask.sum() > 0:
            accuracy = (y_pred_original[mask] == label).sum() / mask.sum()
            print(f"{name} accuracy: {accuracy:.2%}")


def train_hybrid_model(market: str = "KRW-BTC", interval: str = "minute60"):
    """
    하이브리드 모델 학습 메인 함수
    """
    print("="*60)
    print(f"Training Hybrid Model for {market}")
    print("="*60)
    
    # 데이터 로드
    sequence_file = PROCESSED_DIR / f"{market.replace('-', '_')}_{interval}_sequences.npz"
    
    if not sequence_file.exists():
        print(f"Sequence file not found: {sequence_file}")
        return
    
    data = np.load(sequence_file, allow_pickle=True)
    X = data['X']
    y = data['y']
    feature_names = data['feature_names']
    
    print(f"Loaded data: X shape = {X.shape}, y shape = {y.shape}")
    print(f"Number of features: {len(feature_names)}")
    
    # 데이터 정규화
    print("\nNormalizing data...")
    n_samples, seq_length, n_features = X.shape
    X_reshaped = X.reshape(-1, n_features)
    
    scaler = StandardScaler()
    X_normalized = scaler.fit_transform(X_reshaped)
    X = X_normalized.reshape(n_samples, seq_length, n_features)
    
    # Scaler 저장
    with open(MODEL_DIR / "scaler.pkl", 'wb') as f:
        pickle.dump(scaler, f)
    print("Saved scaler")
    
    # Train/Val/Test 분할
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.18, random_state=42)
    
    print(f"\nData split:")
    print(f"  Train: {len(X_train)}")
    print(f"  Val: {len(X_val)}")
    print(f"  Test: {len(X_test)}")
    
    # LSTM 학습
    lstm_model, device, train_losses, val_losses = train_lstm(
        X_train, y_train, X_val, y_val, 
        input_size=n_features,
        epochs=50,
        batch_size=64
    )
    
    # LSTM 특성 추출
    print("\nExtracting LSTM features...")
    lstm_train_features = get_lstm_features(lstm_model, X_train, device)
    lstm_val_features = get_lstm_features(lstm_model, X_val, device)
    lstm_test_features = get_lstm_features(lstm_model, X_test, device)
    
    # LightGBM 학습
    lgb_model = train_lightgbm(lstm_train_features, y_train, lstm_val_features, y_val)
    
    # 평가
    evaluate_model(lstm_model, lgb_model, X_test, y_test, device)
    
    # 메타데이터 저장
    metadata = {
        'market': market,
        'interval': interval,
        'trained_at': datetime.now().isoformat(),
        'n_features': n_features,
        'feature_names': feature_names.tolist(),
        'sequence_length': seq_length,
        'train_size': len(X_train),
        'val_size': len(X_val),
        'test_size': len(X_test),
        'device': str(device)
    }
    
    with open(MODEL_DIR / "model_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Training completed!")
    print(f"Models saved to: {MODEL_DIR}")


def main():
    """
    메인 실행 함수
    """
    # BTC로 학습 (대표 마켓)
    train_hybrid_model(market="KRW-BTC", interval="minute60")


if __name__ == "__main__":
    main()
