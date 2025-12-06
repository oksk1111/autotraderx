"""
강화학습을 위한 트레이딩 환경 (Gym interface)

상태 공간: 시장 데이터 + Layer 1/2 신호
행동 공간: HOLD(0), BUY(1), SELL(2)
보상 함수: 수익률 + 거래 비용 페널티
"""

from __future__ import annotations

import gym
import numpy as np
import pandas as pd
from gym import spaces
from typing import Tuple, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class TradingEnv(gym.Env):
    """
    가상화폐 트레이딩 환경
    
    OpenAI Gym 인터페이스 구현
    """
    
    metadata = {'render.modes': ['human']}
    
    def __init__(
        self,
        market: str = "KRW-BTC",
        data: Optional[pd.DataFrame] = None,
        initial_balance: float = 10_000_000,  # 1000만원
        transaction_fee: float = 0.0005,  # 0.05%
        max_position_size: float = 0.95,  # 최대 95% 투자
    ):
        """
        Args:
            market: 거래 마켓
            data: 백테스팅용 데이터 (None이면 실시간)
            initial_balance: 초기 자본금
            transaction_fee: 거래 수수료율
            max_position_size: 최대 포지션 비율
        """
        super(TradingEnv, self).__init__()
        
        self.market = market
        self.initial_balance = initial_balance
        self.transaction_fee = transaction_fee
        self.max_position_size = max_position_size
        
        # 데이터 설정
        if data is not None:
            self.data = data
            self.use_live_data = False
        else:
            # 실시간 데이터는 RL 학습에 사용 안 함 (백테스트 전용)
            self.use_live_data = True
            self.data = None
        
        # 상태/행동 공간
        # 상태: 46 features + 3 tech_signal + 3 trend_signal = 52
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(52,),
            dtype=np.float32
        )
        
        # 행동: 0=HOLD, 1=BUY, 2=SELL
        self.action_space = spaces.Discrete(3)
        
        # 에피소드 상태
        self.current_step = 0
        self.balance = initial_balance
        self.crypto_held = 0.0
        self.total_trades = 0
        self.buy_count = 0
        self.sell_count = 0
        
        # 성과 추적
        self.total_profit = 0.0
        self.max_balance = initial_balance
        self.max_drawdown = 0.0
        
        logger.info(
            f"TradingEnv initialized: {market}, "
            f"Balance={initial_balance:,.0f}, Fee={transaction_fee:.2%}"
        )
    
    def reset(self) -> np.ndarray:
        """
        환경 초기화
        
        Returns:
            초기 상태
        """
        self.current_step = 0
        self.balance = self.initial_balance
        self.crypto_held = 0.0
        self.total_trades = 0
        self.buy_count = 0
        self.sell_count = 0
        self.total_profit = 0.0
        self.max_balance = self.initial_balance
        self.max_drawdown = 0.0
        
        # 초기 상태 반환
        state = self._get_state()
        return state
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        환경 스텝 실행
        
        Args:
            action: 0=HOLD, 1=BUY, 2=SELL
        
        Returns:
            (next_state, reward, done, info)
        """
        # 현재 가격
        current_price = self._get_current_price()
        
        # 행동 실행
        if action == 1:  # BUY
            self._execute_buy(current_price)
        elif action == 2:  # SELL
            self._execute_sell(current_price)
        # action == 0 (HOLD)는 아무것도 안 함
        
        # 다음 스텝으로 이동
        self.current_step += 1
        
        # 보상 계산
        reward = self._calculate_reward()
        
        # 종료 조건 체크
        done = self._is_done()
        
        # 다음 상태
        next_state = self._get_state()
        
        # 추가 정보
        info = {
            'balance': self.balance,
            'crypto_held': self.crypto_held,
            'total_value': self._get_portfolio_value(),
            'total_trades': self.total_trades,
            'profit': self.total_profit,
            'initial_balance': self.initial_balance
        }
        
        return next_state, reward, done, info
    
    def _get_state(self) -> np.ndarray:
        """
        현재 상태 벡터 생성
        
        Returns:
            52차원 상태 벡터
        """
        # 기본 features (46차원)
        if self.use_live_data or self.data is None:
            # 실시간 데이터 (백테스트 아닐 때)
            features = np.zeros(46)
        else:
            # 백테스팅 데이터
            if self.current_step >= len(self.data):
                features = np.zeros(46)
            else:
                row_values = self.data.iloc[self.current_step].values
                # numpy array로 명시적 변환
                features = np.array(row_values[:46], dtype=np.float32)
        
        # Layer 1 신호 (기술적 지표) - 임시로 중립 신호
        tech_signal = np.array([0, 0, 1], dtype=np.float32)  # HOLD
        
        # Layer 2 신호 (멀티 타임프레임) - 임시로 중립 신호
        trend_signal = np.array([0, 0, 1], dtype=np.float32)  # HOLD
        
        # 통합
        state = np.concatenate([
            features,
            tech_signal,
            trend_signal
        ]).astype(np.float32)
        
        return state
    
    def _get_current_price(self) -> float:
        """현재 시장 가격 조회"""
        if self.use_live_data or self.data is None:
            try:
                from pyupbit import get_current_price
                price = get_current_price(self.market)
                return float(price) if price else 100_000_000.0  # fallback
            except:
                return 100_000_000.0
        else:
            # 백테스팅: 데이터에서 가격 추출
            if self.current_step >= len(self.data):
                return float(self.data.iloc[-1]['close'])
            return float(self.data.iloc[self.current_step]['close'])
    
    def _execute_buy(self, price: float):
        """매수 실행"""
        if self.balance <= 0:
            return  # 잔고 없음
        
        # 최대 포지션 제한
        max_buy_amount = self.balance * self.max_position_size
        
        # 수수료 포함 실제 매수 금액
        buy_amount = max_buy_amount / (1 + self.transaction_fee)
        fee = buy_amount * self.transaction_fee
        
        # 매수 가능 수량
        quantity = buy_amount / price
        
        # 잔고 업데이트
        self.balance -= (buy_amount + fee)
        self.crypto_held += quantity
        self.total_trades += 1
        self.buy_count += 1
        
        logger.debug(
            f"[BUY] Price={price:,.0f}, Qty={quantity:.6f}, "
            f"Cost={buy_amount + fee:,.0f}, Fee={fee:,.0f}"
        )
    
    def _execute_sell(self, price: float):
        """매도 실행"""
        if self.crypto_held <= 0:
            return  # 보유량 없음
        
        # 전량 매도
        sell_amount = self.crypto_held * price
        fee = sell_amount * self.transaction_fee
        
        # 잔고 업데이트
        self.balance += (sell_amount - fee)
        self.crypto_held = 0.0
        self.total_trades += 1
        self.sell_count += 1
        
        logger.debug(
            f"[SELL] Price={price:,.0f}, Amount={sell_amount:,.0f}, Fee={fee:,.0f}"
        )
    
    def _calculate_reward(self) -> float:
        """
        보상 계산
        
        전략:
        1. 포트폴리오 가치 변화 (수익률)
        2. 거래 빈도 페널티 (과도한 거래 방지)
        3. 리스크 관리 (드로우다운 페널티)
        """
        # 현재 포트폴리오 가치
        current_value = self._get_portfolio_value()
        
        # 수익률 (%)
        profit_rate = (current_value - self.initial_balance) / self.initial_balance * 100
        
        # 기본 보상: 수익률
        reward = profit_rate
        
        # 드로우다운 계산
        if current_value > self.max_balance:
            self.max_balance = current_value
        
        drawdown = (self.max_balance - current_value) / self.max_balance * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        # 드로우다운 페널티
        if drawdown > 10:
            reward -= drawdown * 0.5
        
        # 거래 빈도 페널티 (과매매 방지)
        if self.total_trades > 0:
            trade_penalty = self.total_trades * 0.01
            reward -= trade_penalty
        
        return float(reward)
    
    def _get_portfolio_value(self) -> float:
        """현재 포트폴리오 총 가치"""
        current_price = self._get_current_price()
        crypto_value = self.crypto_held * current_price
        return self.balance + crypto_value
    
    def _is_done(self) -> bool:
        """
        에피소드 종료 조건
        
        1. 데이터 끝 도달
        2. 파산 (잔고 0)
        3. 목표 수익 달성 (선택)
        """
        # 데이터 끝
        if not self.use_live_data and self.data is not None and self.current_step >= len(self.data) - 1:
            return True
        
        # 파산
        portfolio_value = self._get_portfolio_value()
        if portfolio_value < self.initial_balance * 0.1:  # 90% 손실
            logger.warning(f"Episode ended: Bankruptcy (Value={portfolio_value:,.0f})")
            return True
        
        # 실시간 모드는 종료 없음
        if self.use_live_data:
            return False
        
        return False
    
    def render(self, mode='human'):
        """환경 상태 출력"""
        portfolio_value = self._get_portfolio_value()
        profit = (portfolio_value - self.initial_balance) / self.initial_balance * 100
        
        print(f"\n=== Step {self.current_step} ===")
        print(f"Balance: {self.balance:,.0f} KRW")
        print(f"Crypto Held: {self.crypto_held:.6f}")
        print(f"Portfolio Value: {portfolio_value:,.0f} KRW")
        print(f"Profit: {profit:+.2f}%")
        print(f"Trades: {self.total_trades} (Buy={self.buy_count}, Sell={self.sell_count})")
        print(f"Max Drawdown: {self.max_drawdown:.2f}%")


class BacktestTradingEnv(TradingEnv):
    """
    백테스팅용 트레이딩 환경
    
    과거 데이터를 사용하여 RL 에이전트 학습
    """
    
    def __init__(
        self,
        market: str = "KRW-BTC",
        data_path: Optional[str] = None,
        **kwargs
    ):
        """
        Args:
            market: 마켓 코드
            data_path: CSV 데이터 경로
            **kwargs: TradingEnv 파라미터
        """
        # 데이터 로딩
        if data_path:
            data = pd.read_csv(data_path)
        else:
            # 기본 데이터 경로
            default_path = f"/app/data/processed/{market.replace('-', '_')}_1h_processed.csv"
            data = pd.read_csv(default_path)
        
        # 필요한 컬럼만 선택
        if 'timestamp' in data.columns:
            data = data.sort_values('timestamp')
        
        super().__init__(
            market=market,
            data=data,
            **kwargs
        )
        
        logger.info(f"BacktestEnv initialized with {len(data)} data points")


class LiveTradingEnv(TradingEnv):
    """
    실시간 트레이딩 환경
    
    실제 시장 데이터를 사용하여 RL 에이전트 실행
    """
    
    def __init__(self, market: str = "KRW-BTC", **kwargs):
        super().__init__(
            market=market,
            data=None,  # 실시간 데이터 사용
            **kwargs
        )
        logger.info("LiveTradingEnv initialized")
