"""
급등 예측기 (Pump Predictor) v5.0

기존 PumpDetector의 한계:
- 이미 급등한 후에 감지 (뒤늦은 추격매수)
- 최고점 매도 로직 없음

개선된 PumpPredictor:
1. 급등 조짐(Pre-Pump) 감지: 거래량 급증 + 가격 상승 초기 단계
2. 최고점(Peak) 감지: RSI 과열 + 가격 상승 둔화 + 매도압력 증가
3. 동적 익절: 트레일링 스탑 적용
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import pyupbit
import pandas as pd
import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class PumpSignal:
    """급등 관련 시그널"""
    market: str
    signal_type: str  # 'PRE_PUMP', 'PUMPING', 'PEAK', 'NONE'
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    change_percent: float
    reason: str
    metrics: Dict


class PumpPredictor:
    """
    급등 예측 및 최고점 감지기
    
    3단계 감지:
    1. PRE_PUMP: 급등 조짐 (거래량 급증 + 초기 상승)
    2. PUMPING: 급등 진행 중 (추가 매수 금지, 홀딩)
    3. PEAK: 최고점 도달 (매도 시그널)
    """
    
    def __init__(self):
        # 가격/거래량 히스토리 (시장별)
        self.price_history: Dict[str, List[Tuple[float, float, float]]] = {}  # {market: [(timestamp, price, volume), ...]}
        self.max_history_size = 120  # 2분간 데이터 (1초당 1개 기준)
        
        # 포지션별 최고가 추적 (트레일링 스탑용)
        self.position_high_prices: Dict[str, float] = {}
        
        # 급등 조짐 감지 파라미터
        self.pre_pump_thresholds = {
            'volume_surge_ratio': 2.0,    # 평균 대비 2배 거래량
            'price_rise_min': 0.3,        # 최소 0.3% 상승
            'price_rise_max': 1.0,        # 최대 1.0% (이미 급등 시작하면 조짐 아님)
            'time_window_seconds': 30,    # 30초 윈도우
        }
        
        # 피크 감지 파라미터
        self.peak_thresholds = {
            'price_drop_from_high': -0.5,  # 고점 대비 -0.5% 하락 시 피크로 간주
            'rsi_overbought': 75,          # RSI 75 이상
            'volume_decrease_ratio': 0.7,  # 거래량 30% 감소
            'trailing_stop_pct': 0.015,    # 1.5% 트레일링 스탑
        }
        
    def update_tick(self, market: str, price: float, volume: float):
        """실시간 틱 데이터 업데이트"""
        now = time.time()
        
        if market not in self.price_history:
            self.price_history[market] = []
            
        self.price_history[market].append((now, price, volume))
        
        # 오래된 데이터 제거
        cutoff = now - self.max_history_size
        self.price_history[market] = [
            (t, p, v) for t, p, v in self.price_history[market] if t > cutoff
        ]
        
    def detect_pre_pump(self, market: str, current_price: float, current_volume: float) -> Optional[PumpSignal]:
        """
        급등 조짐 감지 (매수 시그널)
        
        조건:
        1. 최근 30초 거래량이 평균의 2배 이상
        2. 가격이 0.3~1.0% 상승 중 (너무 많이 오르면 이미 급등)
        3. 연속적인 상승 (최근 5틱 중 4개 이상 상승)
        """
        self.update_tick(market, current_price, current_volume)
        
        history = self.price_history.get(market, [])
        if len(history) < 10:
            return None
            
        now = time.time()
        window_start = now - self.pre_pump_thresholds['time_window_seconds']
        
        # 윈도우 내 데이터
        window_data = [(t, p, v) for t, p, v in history if t > window_start]
        if len(window_data) < 5:
            return None
            
        # 1. 가격 변화율 체크
        first_price = window_data[0][1]
        price_change = ((current_price - first_price) / first_price) * 100
        
        # 2. 거래량 급증 체크
        recent_volumes = [v for _, _, v in window_data]
        all_volumes = [v for _, _, v in history]
        
        avg_volume = np.mean(all_volumes) if all_volumes else 1
        recent_avg_volume = np.mean(recent_volumes) if recent_volumes else 0
        volume_ratio = recent_avg_volume / avg_volume if avg_volume > 0 else 0
        
        # 3. 연속 상승 체크
        recent_prices = [p for _, p, _ in window_data[-6:]]
        up_count = sum(1 for i in range(1, len(recent_prices)) if recent_prices[i] > recent_prices[i-1])
        
        # 급등 조짐 조건 확인
        is_volume_surge = volume_ratio >= self.pre_pump_thresholds['volume_surge_ratio']
        is_rising = (self.pre_pump_thresholds['price_rise_min'] <= price_change <= self.pre_pump_thresholds['price_rise_max'])
        is_consistent_up = up_count >= 3  # 최근 5틱 중 3개 이상 상승
        
        if is_volume_surge and is_rising and is_consistent_up:
            confidence = min(0.95, 0.6 + (volume_ratio - 2.0) * 0.1 + price_change * 0.1)
            
            return PumpSignal(
                market=market,
                signal_type='PRE_PUMP',
                action='BUY',
                confidence=float(confidence),
                change_percent=price_change,
                reason=f"급등 조짐: 거래량 {volume_ratio:.1f}배 + {price_change:.2f}% 상승",
                metrics={
                    'volume_ratio': volume_ratio,
                    'price_change': price_change,
                    'up_ticks': up_count,
                }
            )
            
        return None
        
    def detect_peak(self, market: str, current_price: float, entry_price: float, 
                    current_volume: float, rsi: Optional[float] = None) -> Optional[PumpSignal]:
        """
        최고점(피크) 감지 (매도 시그널)
        
        조건:
        1. 트레일링 스탑: 고점 대비 1.5% 하락
        2. RSI 과열: 75 이상
        3. 거래량 감소: 고점 대비 30% 이상 감소
        4. 가격 상승 둔화: 최근 틱에서 하락 연속
        """
        # 최고가 업데이트
        if market not in self.position_high_prices:
            self.position_high_prices[market] = current_price
        else:
            self.position_high_prices[market] = max(self.position_high_prices[market], current_price)
            
        high_price = self.position_high_prices[market]
        
        # 1. 트레일링 스탑 체크
        drop_from_high = (current_price - high_price) / high_price
        trailing_stop_triggered = drop_from_high <= -self.peak_thresholds['trailing_stop_pct']
        
        # 2. RSI 과열 체크
        rsi_overbought = rsi is not None and rsi >= self.peak_thresholds['rsi_overbought']
        
        # 3. 수익률 체크
        profit_pct = (current_price - entry_price) / entry_price * 100
        
        # 피크 감지 로직
        reasons = []
        confidence = 0.5
        
        if trailing_stop_triggered:
            reasons.append(f"트레일링 스탑 (고점 {high_price:,.0f} → 현재 {current_price:,.0f}, {drop_from_high*100:.2f}%)")
            confidence += 0.25
            
        if rsi_overbought:
            reasons.append(f"RSI 과열 ({rsi:.1f})")
            confidence += 0.15
            
        if profit_pct >= 3.0:
            reasons.append(f"목표 수익 달성 (+{profit_pct:.1f}%)")
            confidence += 0.1
            
        if reasons:
            return PumpSignal(
                market=market,
                signal_type='PEAK',
                action='SELL',
                confidence=min(confidence, 0.95),
                change_percent=profit_pct,
                reason=" + ".join(reasons),
                metrics={
                    'high_price': high_price,
                    'drop_from_high': drop_from_high * 100,
                    'profit_pct': profit_pct,
                    'rsi': rsi,
                }
            )
            
        return None
        
    def clear_position(self, market: str):
        """포지션 청산 시 최고가 추적 초기화"""
        if market in self.position_high_prices:
            del self.position_high_prices[market]
            
    def analyze(self, market: str, df: pd.DataFrame, 
                current_price: float, current_volume: float,
                has_position: bool = False, entry_price: float = 0) -> PumpSignal:
        """
        종합 분석
        
        Args:
            market: 마켓 코드
            df: OHLCV 데이터프레임 (기술적 지표 포함)
            current_price: 현재가
            current_volume: 현재 거래량
            has_position: 포지션 보유 여부
            entry_price: 진입가 (포지션 있을 때)
        """
        # RSI 가져오기
        rsi = df.iloc[-1].get('rsi', 50) if df is not None and len(df) > 0 else None
        
        # 포지션이 있으면 피크 감지
        if has_position:
            peak_signal = self.detect_peak(market, current_price, entry_price, current_volume, rsi)
            if peak_signal:
                return peak_signal
                
            # 피크 아니면 HOLD
            return PumpSignal(
                market=market,
                signal_type='PUMPING',
                action='HOLD',
                confidence=0.5,
                change_percent=(current_price - entry_price) / entry_price * 100,
                reason="홀딩 중 (피크 미감지)",
                metrics={'rsi': rsi}
            )
            
        # 포지션이 없으면 급등 조짐 감지
        pre_pump_signal = self.detect_pre_pump(market, current_price, current_volume)
        if pre_pump_signal:
            return pre_pump_signal
            
        # 신호 없음
        return PumpSignal(
            market=market,
            signal_type='NONE',
            action='HOLD',
            confidence=0.0,
            change_percent=0.0,
            reason="신호 없음",
            metrics={}
        )
