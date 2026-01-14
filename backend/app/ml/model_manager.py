"""
다중 코인 모델 관리
각 마켓별로 별도의 모델을 로드하고 관리
"""
import pickle
from pathlib import Path
from typing import Dict, Optional

import lightgbm as lgb
import numpy as np
try:
    import torch
    ML_AVAILABLE = True
except ImportError:
    import logging
    logging.getLogger(__name__).warning("Torch not found. ModelManager disabled.")
    ML_AVAILABLE = False
    
from app.core.logging import get_logger
from app.ml.predictor import LSTMModel, MLSignal

logger = get_logger(__name__)


class MultiCoinModelManager:
    """
    여러 코인에 대한 모델을 관리하는 클래스
    각 마켓별로 LSTM + LightGBM + Scaler를 로드
    """
    
    def __init__(self, model_base_dir: str = "/app/models"):
        self.model_base_dir = Path(model_base_dir)
        if ML_AVAILABLE:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = "cpu"
        
        # 마켓별 모델 저장소
        self.models: Dict[str, Dict[str, any]] = {}
        
        # 지원하는 마켓 목록
        self.supported_markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]
        
        logger.info(f"MultiCoinModelManager initialized with device: {self.device}")
    
    def load_model_for_market(self, market: str) -> bool:
        """
        특정 마켓의 모델을 로드
        
        Args:
            market: 마켓 코드 (예: "KRW-BTC")
        
        Returns:
            성공 여부
        """
        if not ML_AVAILABLE:
            return False

        # 이미 로드된 경우
        if market in self.models:
            logger.debug(f"Model for {market} already loaded")
            return True
        
        # 기본 디렉토리를 먼저 시도 (단일 모델인 경우)
        market_dir = self.model_base_dir
        
        # 마켓별 디렉토리가 존재하면 사용 (예: /app/models/KRW_BTC/)
        market_specific_dir = self.model_base_dir / market.replace("-", "_")
        if market_specific_dir.exists():
            market_dir = market_specific_dir
        
        try:
            lstm_path = market_dir / "lstm_best.pth"
            lgb_path = market_dir / "lightgbm_model.txt"
            scaler_path = market_dir / "scaler.pkl"
            
            if not (lstm_path.exists() and lgb_path.exists() and scaler_path.exists()):
                logger.warning(f"Model files not found for {market} in {market_dir}")
                return False
            
            # LSTM 로드
            lstm_model = LSTMModel(input_size=46, hidden_size=128, num_layers=2, dropout=0.3)
            lstm_model.load_state_dict(torch.load(lstm_path, map_location=self.device))
            lstm_model.to(self.device)
            lstm_model.eval()
            
            # LightGBM 로드
            lgb_model = lgb.Booster(model_file=str(lgb_path))
            
            # Scaler 로드
            with open(scaler_path, 'rb') as f:
                scaler = pickle.load(f)
            
            # 저장
            self.models[market] = {
                "lstm": lstm_model,
                "lgb": lgb_model,
                "scaler": scaler,
                "model_dir": str(market_dir)
            }
            
            logger.info(f"Successfully loaded model for {market} from {market_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model for {market}: {e}", exc_info=True)
            return False
    
    def load_all_models(self):
        """모든 지원 마켓의 모델 로드"""
        for market in self.supported_markets:
            self.load_model_for_market(market)
        
        loaded_count = len(self.models)
        logger.info(f"Loaded {loaded_count}/{len(self.supported_markets)} models")
    
    def predict(self, market: str, sequence: np.ndarray) -> Optional[MLSignal]:
        """
        특정 마켓에 대한 예측 수행
        
        Args:
            market: 마켓 코드
            sequence: (24, 46) 형태의 시계열 데이터
        
        Returns:
            MLSignal 또는 None (모델이 없는 경우)
        """
        # 모델 로드 시도
        if market not in self.models:
            if not self.load_model_for_market(market):
                logger.warning(f"Cannot predict for {market}: model not available")
                return None
        
        try:
            model_dict = self.models[market]
            lstm_model = model_dict["lstm"]
            lgb_model = model_dict["lgb"]
            scaler = model_dict["scaler"]
            
            # 정규화
            if len(sequence.shape) == 2:
                # (24, 46) -> (24*46,) -> normalize -> (24, 46)
                sequence_flat = sequence.reshape(-1, 46)
                sequence_normalized = scaler.transform(sequence_flat)
                sequence_normalized = sequence_normalized.reshape(1, 24, 46)
            else:
                sequence_normalized = sequence.reshape(1, 24, 46)
            
            # LSTM 예측
            with torch.no_grad():
                sequence_tensor = torch.FloatTensor(sequence_normalized).to(self.device)
                lstm_features = lstm_model(sequence_tensor).cpu().numpy()
            
            # LightGBM 예측
            probabilities = lgb_model.predict(lstm_features)[0]  # [sell_prob, hold_prob, buy_prob]
            
            # 확률 추출
            sell_prob = float(probabilities[0])
            hold_prob = float(probabilities[1])
            buy_prob = float(probabilities[2])
            
            # 신뢰도 계산
            sorted_probs = sorted([sell_prob, hold_prob, buy_prob], reverse=True)
            confidence = sorted_probs[0] - sorted_probs[1]
            
            # 긴급 점수 (Sell 확률이 높고 신뢰도가 높을수록)
            emergency_score = sell_prob * confidence
            
            logger.debug(
                f"Prediction for {market}: Buy={buy_prob:.3f}, Sell={sell_prob:.3f}, "
                f"Hold={hold_prob:.3f}, Confidence={confidence:.3f}"
            )
            
            return MLSignal(
                market=market,
                buy_probability=buy_prob,
                sell_probability=sell_prob,
                emergency_score=emergency_score,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error during prediction for {market}: {e}", exc_info=True)
            return None
    
    def is_model_available(self, market: str) -> bool:
        """특정 마켓의 모델이 사용 가능한지 확인"""
        return market in self.models
    
    def get_loaded_markets(self) -> list:
        """로드된 마켓 목록 반환"""
        return list(self.models.keys())
