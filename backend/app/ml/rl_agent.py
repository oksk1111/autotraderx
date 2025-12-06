"""
강화학습 트레이딩 에이전트 (Layer 3)
PPO(Proximal Policy Optimization) 알고리즘 사용

상태 공간:
- 시장 features (46차원)
- Layer 1 신호 (3차원 - BUY/SELL/HOLD)
- Layer 2 신호 (3차원)
총 52차원

행동 공간:
- 0: HOLD
- 1: BUY
- 2: SELL
"""

from __future__ import annotations

import os
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict

from app.core.logging import get_logger

logger = get_logger(__name__)


class RLTradingAgent:
    """
    강화학습 기반 트레이딩 에이전트
    
    PPO 알고리즘을 사용하여 최적의 매매 타이밍 학습
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Args:
            model_path: 학습된 모델 경로 (없으면 신규 생성)
        """
        self.model_path = model_path or self._get_default_model_path()
        self.model = None
        self.is_trained = False
        
        # 상태/행동 공간 설정
        self.state_dim = 52  # 46 features + 3 tech + 3 trend
        self.action_dim = 3  # HOLD, BUY, SELL
        
        # 행동 매핑
        self.action_to_signal = {
            0: "HOLD",
            1: "BUY",
            2: "SELL"
        }
        
        self._load_model()
    
    def _get_default_model_path(self) -> str:
        """기본 모델 저장 경로"""
        return "/app/models/rl_agent_ppo.zip"
    
    def _load_model(self):
        """학습된 모델 로딩"""
        try:
            # stable-baselines3 임포트
            from stable_baselines3 import PPO
            
            if os.path.exists(self.model_path):
                self.model = PPO.load(self.model_path)
                self.is_trained = True
                logger.info(f"✅ RL Agent loaded from {self.model_path}")
            else:
                logger.warning(f"⚠️ RL model not found at {self.model_path}")
                logger.info("RL Agent는 학습 후 사용 가능합니다.")
                self.is_trained = False
        
        except ImportError:
            logger.warning("stable-baselines3 not installed. RL Agent disabled.")
            self.is_trained = False
        except Exception as e:
            logger.error(f"Failed to load RL model: {e}")
            self.is_trained = False
    
    def predict(self, state: np.ndarray) -> Tuple[str, float]:
        """
        주어진 상태에서 최적 행동 예측
        
        Args:
            state: 상태 벡터 (52차원)
        
        Returns:
            (action, confidence)
            - action: BUY, SELL, HOLD
            - confidence: 0.0 ~ 1.0
        """
        if not self.is_trained or self.model is None:
            # 학습 안 된 경우 기본값
            return "HOLD", 0.3
        
        try:
            # 상태 차원 검증
            if state.shape[0] != self.state_dim:
                logger.error(
                    f"Invalid state dimension: {state.shape[0]} "
                    f"(expected {self.state_dim})"
                )
                return "HOLD", 0.3
            
            # 예측 수행
            action, _states = self.model.predict(state, deterministic=True)
            
            # 신뢰도 계산 (정책 네트워크의 확률 분포 사용)
            # PPO는 stochastic policy이므로 action probability 추출
            obs_tensor = self.model.policy.obs_to_tensor(state.reshape(1, -1))[0]
            distribution = self.model.policy.get_distribution(obs_tensor)
            probs = distribution.distribution.probs.detach().cpu().numpy()[0]
            
            confidence = float(probs[action])
            signal = self.action_to_signal[int(action)]
            
            logger.debug(f"[RL] Action={signal}, Confidence={confidence:.1%}")
            
            return signal, confidence
        
        except Exception as e:
            logger.error(f"RL prediction error: {e}")
            return "HOLD", 0.3
    
    def get_action_probs(self, state: np.ndarray) -> Dict[str, float]:
        """
        모든 행동에 대한 확률 분포 반환
        
        Args:
            state: 상태 벡터
        
        Returns:
            {'HOLD': 0.6, 'BUY': 0.3, 'SELL': 0.1}
        """
        if not self.is_trained or self.model is None:
            return {"HOLD": 0.6, "BUY": 0.2, "SELL": 0.2}
        
        try:
            obs_tensor = self.model.policy.obs_to_tensor(state.reshape(1, -1))[0]
            distribution = self.model.policy.get_distribution(obs_tensor)
            probs = distribution.distribution.probs.detach().cpu().numpy()[0]
            
            return {
                "HOLD": float(probs[0]),
                "BUY": float(probs[1]),
                "SELL": float(probs[2])
            }
        
        except Exception as e:
            logger.error(f"Failed to get action probs: {e}")
            return {"HOLD": 0.6, "BUY": 0.2, "SELL": 0.2}
    
    def is_available(self) -> bool:
        """RL 에이전트 사용 가능 여부"""
        return self.is_trained and self.model is not None


# === 학습용 헬퍼 함수 ===

def train_rl_agent(
    env,
    total_timesteps: int = 100_000,
    save_path: Optional[str] = None,
    learning_rate: float = 3e-4,
    n_steps: int = 2048,
    batch_size: int = 64,
    n_epochs: int = 10,
    gamma: float = 0.99,
    verbose: int = 1
) -> RLTradingAgent:
    """
    RL 에이전트 학습
    
    Args:
        env: 트레이딩 환경 (Gym interface)
        total_timesteps: 총 학습 스텝 수
        save_path: 모델 저장 경로
        learning_rate: 학습률
        n_steps: 한 업데이트당 스텝 수
        batch_size: 배치 크기
        n_epochs: PPO 업데이트 epoch 수
        gamma: 할인율
        verbose: 로그 레벨
    
    Returns:
        학습된 RLTradingAgent
    """
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import CheckpointCallback
        
        # 모델 생성
        model = PPO(
            "MlpPolicy",
            env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            verbose=verbose,
            tensorboard_log="/app/logs/tensorboard/"
        )
        
        # 체크포인트 콜백
        save_path = save_path or "/app/models/rl_agent_ppo"
        checkpoint_callback = CheckpointCallback(
            save_freq=10000,
            save_path="/app/models/checkpoints/",
            name_prefix="rl_agent"
        )
        
        logger.info(f"🚀 Starting RL training for {total_timesteps} timesteps...")
        
        # 학습 시작
        model.learn(
            total_timesteps=total_timesteps,
            callback=checkpoint_callback,
            progress_bar=True
        )
        
        # 모델 저장
        model.save(save_path)
        logger.info(f"✅ Model saved to {save_path}.zip")
        
        # RLTradingAgent로 래핑
        agent = RLTradingAgent(model_path=f"{save_path}.zip")
        
        return agent
    
    except ImportError:
        logger.error(
            "stable-baselines3 not installed. "
            "Install with: pip install stable-baselines3"
        )
        raise
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


def evaluate_rl_agent(
    agent: RLTradingAgent,
    env,
    n_episodes: int = 10
) -> Dict[str, float]:
    """
    RL 에이전트 성능 평가
    
    Args:
        agent: 학습된 에이전트
        env: 평가 환경
        n_episodes: 평가 에피소드 수
    
    Returns:
        평가 지표 딕셔너리
    """
    total_rewards = []
    total_profits = []
    win_counts = 0
    
    for episode in range(n_episodes):
        obs = env.reset()
        done = False
        episode_reward = 0
        
        while not done:
            # 에이전트 예측
            action_signal, confidence = agent.predict(obs)
            
            # 행동 변환 (signal → action_id)
            action_map = {"HOLD": 0, "BUY": 1, "SELL": 2}
            action = action_map[action_signal]
            
            # 환경 스텝
            obs, reward, done, info = env.step(action)
            episode_reward += reward
        
        total_rewards.append(episode_reward)
        
        # 최종 수익 계산
        final_balance = info.get('balance', 0)
        initial_balance = info.get('initial_balance', 10_000_000)
        profit = (final_balance - initial_balance) / initial_balance * 100
        
        total_profits.append(profit)
        if profit > 0:
            win_counts += 1
    
    # 평가 지표 계산
    metrics = {
        'avg_reward': float(np.mean(total_rewards)),
        'std_reward': float(np.std(total_rewards)),
        'avg_profit': float(np.mean(total_profits)),
        'std_profit': float(np.std(total_profits)),
        'win_rate': win_counts / n_episodes,
        'max_profit': float(np.max(total_profits)),
        'min_profit': float(np.min(total_profits))
    }
    
    logger.info("=== RL Agent Evaluation ===")
    logger.info(f"Episodes: {n_episodes}")
    logger.info(f"Avg Reward: {metrics['avg_reward']:.2f} ± {metrics['std_reward']:.2f}")
    logger.info(f"Avg Profit: {metrics['avg_profit']:.2f}% ± {metrics['std_profit']:.2f}%")
    logger.info(f"Win Rate: {metrics['win_rate']:.1%}")
    logger.info(f"Profit Range: [{metrics['min_profit']:.2f}%, {metrics['max_profit']:.2f}%]")
    
    return metrics
