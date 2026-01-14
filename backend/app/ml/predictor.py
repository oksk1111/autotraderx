from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union

import lightgbm as lgb
import numpy as np
import torch
import torch.nn as nn

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MLSignal:
    market: str
    buy_probability: float
    sell_probability: float
    emergency_score: float
    confidence: float = 0.0

    @property
    def action(self) -> str:
        if self.buy_probability > self.sell_probability and self.buy_probability > 0.55:
            return "BUY"
        if self.sell_probability > self.buy_probability and self.sell_probability > 0.55:
            return "SELL"
        return "HOLD"


class LSTMModel(nn.Module):
    """LSTM 기반 시계열 예측 모델"""
    
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


class HybridPredictor:
    """LSTM + LightGBM 하이브리드 예측 엔진"""

    def __init__(self, model_dir: str = "/app/models", settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model_dir = Path(model_dir)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # 단일 모델 로딩 (레거시 지원)
        self.lstm_model = None
        self.lgb_model = None
        self.scaler = None
        
        # 다중 코인 모델 매니저 (지연 로딩)
        self._model_manager = None
        
        try:
            # 설정 확인: ML 모델 사용 비활성화 시 로딩 스킵
            if hasattr(self.settings, 'use_ml_models') and not self.settings.use_ml_models:
                logger.info("ML models are disabled by configuration (use_ml_models=False). Skipping model loading.")
                self.lstm_model = None
                self.lgb_model = None
                self.scaler = None
                return

            self._load_models()
            logger.info(f"Models loaded successfully from {model_dir} on {self.device}")
        except Exception as e:
            logger.warning(f"Failed to load models: {e}. Using fallback predictions.")
    
    @property
    def model_manager(self):
        """모델 매니저 lazy loading"""
        if self._model_manager is None:
            from app.ml.model_manager import MultiCoinModelManager
            self._model_manager = MultiCoinModelManager(str(self.model_dir))
            # 초기화 시 모든 모델 로드 시도
            self._model_manager.load_all_models()
        return self._model_manager
    
    def _load_models(self):
        """기본 모델 파일 로드 (단일 모델 레거시 지원)"""
        # LSTM 모델 로드
        lstm_path = self.model_dir / "lstm_best.pth"
        if lstm_path.exists():
            self.lstm_model = LSTMModel(input_size=46, hidden_size=128, num_layers=2, dropout=0.3)
            self.lstm_model.load_state_dict(torch.load(lstm_path, map_location=self.device))
            self.lstm_model.to(self.device)
            self.lstm_model.eval()
            logger.info(f"LSTM model loaded from {lstm_path}")
        
        # LightGBM 모델 로드
        lgb_path = self.model_dir / "lightgbm_model.txt"
        if lgb_path.exists():
            self.lgb_model = lgb.Booster(model_file=str(lgb_path))
            logger.info(f"LightGBM model loaded from {lgb_path}")
        
        # StandardScaler 로드
        scaler_path = self.model_dir / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            logger.info(f"StandardScaler loaded from {scaler_path}")

    def infer(self, features: Dict[str, Union[float, str]]) -> MLSignal:
        """
        특징을 기반으로 예측 수행
        
        Args:
            features: 시장 데이터 특징. 다음 중 하나의 형식:
                - {"market": "KRW-BTC", "sequence": numpy array (24, 46)}
                - 기타 dict (레거시, 기본값 반환)
        
        Returns:
            MLSignal: 예측 결과
        """
        market = str(features.get("market", "KRW-BTC"))
        
        # ML 모델이 비활성화되었거나 로드되지 않은 경우 기본값(중립) 반환
        if (hasattr(self.settings, 'use_ml_models') and not self.settings.use_ml_models) or \
           (self.lstm_model is None and self.lgb_model is None and self._model_manager is None):
            return MLSignal(
                market=market,
                buy_probability=0.0,
                sell_probability=0.0,
                emergency_score=0.0,
                confidence=0.0
            )

        sequence = features.get("sequence")
        
        # 시퀀스가 제공된 경우 다중 코인 모델 매니저 사용
        if sequence is not None and isinstance(sequence, np.ndarray):
            try:
                result = self.model_manager.predict(market, sequence)
                if result is not None:
                    return result
                else:
                    logger.warning(f"Model prediction failed for {market}, using fallback")
            except Exception as e:
                logger.error(f"Error in model_manager.predict: {e}", exc_info=True)
        
        # 레거시 단일 모델 로직 (또는 시퀀스가 없는 경우)
        if self.lstm_model is None or self.lgb_model is None or self.scaler is None:
            logger.warning("Models not loaded, returning default predictions")
            return MLSignal(
                market=market,
                buy_probability=0.33,
                sell_probability=0.33,
                emergency_score=0.0,
                confidence=0.0
            )
        
        try:
            # 시퀀스 검증
            if sequence is None or not isinstance(sequence, np.ndarray):
                logger.warning(
                    f"Invalid sequence data for {market}: "
                    f"type={type(sequence)}, is_ndarray={isinstance(sequence, np.ndarray) if sequence is not None else False}"
                )
                return MLSignal(
                    market=market,
                    buy_probability=0.33,
                    sell_probability=0.33,
                    emergency_score=0.0,
                    confidence=0.0
                )
            
            # 형상 및 NaN 검증
            expected_shape = (24, 46)
            if sequence.shape != expected_shape:
                logger.warning(
                    f"Invalid sequence shape for {market}: expected {expected_shape}, got {sequence.shape}"
                )
                return MLSignal(
                    market=market,
                    buy_probability=0.33,
                    sell_probability=0.33,
                    emergency_score=0.0,
                    confidence=0.0
                )
            
            nan_count = np.isnan(sequence).sum()
            if nan_count > 0:
                logger.warning(
                    f"Sequence contains {nan_count} NaN values for {market}, using default predictions"
                )
                return MLSignal(
                    market=market,
                    buy_probability=0.33,
                    sell_probability=0.33,
                    emergency_score=0.0,
                    confidence=0.0
                )
            
            # 정규화
            original_shape = sequence.shape
            if len(original_shape) == 2:
                # (24, 46) -> (24*46,) -> normalize -> (24, 46)
                sequence_flat = sequence.reshape(-1, 46)
                sequence_normalized = self.scaler.transform(sequence_flat)
                sequence_normalized = sequence_normalized.reshape(1, 24, 46)
            else:
                sequence_normalized = sequence.reshape(1, 24, 46)
            
            # LSTM 예측
            with torch.no_grad():
                sequence_tensor = torch.FloatTensor(sequence_normalized).to(self.device)
                lstm_features = self.lstm_model(sequence_tensor).cpu().numpy()
            
            # LightGBM 예측
            probabilities = self.lgb_model.predict(lstm_features)[0]  # [sell_prob, hold_prob, buy_prob]
            
            # 확률 추출
            sell_prob = float(probabilities[0])
            hold_prob = float(probabilities[1])
            buy_prob = float(probabilities[2])
            
            # 신뢰도 계산 (최대 확률 - 두번째로 높은 확률)
            sorted_probs = sorted([sell_prob, hold_prob, buy_prob], reverse=True)
            confidence = sorted_probs[0] - sorted_probs[1]
            
            # 긴급 점수 계산 (Sell 확률이 높고 신뢰도가 높을수록)
            emergency_score = sell_prob * confidence
            
            logger.debug(
                f"ML prediction for {market}: Buy={buy_prob:.3f}, Sell={sell_prob:.3f}, "
                f"Hold={hold_prob:.3f}, Confidence={confidence:.3f}, Emergency={emergency_score:.3f}"
            )
            
            return MLSignal(
                market=market,
                buy_probability=buy_prob,
                sell_probability=sell_prob,
                emergency_score=emergency_score,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error during inference: {e}", exc_info=True)
            return MLSignal(
                market=market,
                buy_probability=0.33,
                sell_probability=0.33,
                emergency_score=0.0,
                confidence=0.0
            )

    def emergency_triggered(self, emergency_score: float) -> bool:
        """긴급 매도 조건 판단"""
        return emergency_score > 0.7  # 0.9에서 0.7로 하향 조정 (더 민감하게)
