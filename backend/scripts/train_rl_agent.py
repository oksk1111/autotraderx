#!/usr/bin/env python3
"""
RL Agent 학습 스크립트

PPO 알고리즘으로 트레이딩 에이전트 학습
백테스팅 데이터 사용하여 100,000 timesteps 학습
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import pandas as pd
from datetime import datetime

from app.ml.trading_env import BacktestTradingEnv
from app.ml.rl_agent import train_rl_agent, evaluate_rl_agent
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Train RL Trading Agent')
    parser.add_argument(
        '--market',
        type=str,
        default='KRW-BTC',
        help='Market to trade (default: KRW-BTC)'
    )
    parser.add_argument(
        '--data-path',
        type=str,
        default=None,
        help='Path to training data CSV (default: /app/data/processed/{market}_1h_processed.csv)'
    )
    parser.add_argument(
        '--timesteps',
        type=int,
        default=100_000,
        help='Total training timesteps (default: 100,000)'
    )
    parser.add_argument(
        '--initial-balance',
        type=float,
        default=10_000_000,
        help='Initial balance in KRW (default: 10,000,000)'
    )
    parser.add_argument(
        '--learning-rate',
        type=float,
        default=3e-4,
        help='Learning rate (default: 3e-4)'
    )
    parser.add_argument(
        '--save-path',
        type=str,
        default='/app/models/rl_agent_ppo',
        help='Path to save trained model (default: /app/models/rl_agent_ppo)'
    )
    parser.add_argument(
        '--eval-episodes',
        type=int,
        default=10,
        help='Number of evaluation episodes (default: 10)'
    )
    parser.add_argument(
        '--no-eval',
        action='store_true',
        help='Skip evaluation after training'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("RL Trading Agent Training")
    logger.info("=" * 60)
    logger.info(f"Market: {args.market}")
    logger.info(f"Timesteps: {args.timesteps:,}")
    logger.info(f"Initial Balance: {args.initial_balance:,.0f} KRW")
    logger.info(f"Learning Rate: {args.learning_rate}")
    logger.info(f"Save Path: {args.save_path}")
    logger.info("=" * 60)
    
    # 데이터 경로 설정
    if args.data_path is None:
        market_file = args.market.replace('-', '_')
        args.data_path = f"/app/data/processed/{market_file}_1h_processed.csv"
    
    # 데이터 존재 확인
    if not os.path.exists(args.data_path):
        logger.error(f"Data file not found: {args.data_path}")
        logger.info("Please run data collection and processing first:")
        logger.info("  python /app/scripts/collect_data.py")
        logger.info("  python /app/scripts/prepare_features.py")
        return 1
    
    try:
        # 학습 환경 생성
        logger.info(f"Loading training data from {args.data_path}...")
        train_env = BacktestTradingEnv(
            market=args.market,
            data_path=args.data_path,
            initial_balance=args.initial_balance
        )
        
        # 데이터 통계
        data_size = len(train_env.data)
        logger.info(f"Training data loaded: {data_size} rows")
        
        # 학습 시작
        start_time = datetime.now()
        logger.info(f"Training started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        agent = train_rl_agent(
            env=train_env,
            total_timesteps=args.timesteps,
            save_path=args.save_path,
            learning_rate=args.learning_rate,
            verbose=1
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info(f"✅ Training completed!")
        logger.info(f"Duration: {duration:.0f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"Model saved to: {args.save_path}.zip")
        logger.info("=" * 60)
        
        # 평가
        if not args.no_eval:
            logger.info("\n🔍 Evaluating trained agent...")
            
            # 평가 환경 (학습 데이터와 다른 구간 사용)
            eval_env = BacktestTradingEnv(
                market=args.market,
                data_path=args.data_path,
                initial_balance=args.initial_balance
            )
            
            metrics = evaluate_rl_agent(
                agent=agent,
                env=eval_env,
                n_episodes=args.eval_episodes
            )
            
            logger.info("=" * 60)
            logger.info("Evaluation Summary:")
            logger.info(f"  Avg Profit: {metrics['avg_profit']:.2f}%")
            logger.info(f"  Win Rate: {metrics['win_rate']:.1%}")
            logger.info(f"  Max Profit: {metrics['max_profit']:.2f}%")
            logger.info(f"  Min Profit: {metrics['min_profit']:.2f}%")
            logger.info("=" * 60)
        
        logger.info("\n✨ All done! RL agent is ready to use.")
        logger.info("To use the agent, set use_rl=True in Enhanced Engine.")
        
        return 0
    
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
