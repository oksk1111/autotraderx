"""
긴급 거래 시스템
- 급락/급등 실시간 감지
- 정규 매매 주기와 독립적으로 10초마다 체크
- 위험 상황 시 즉시 매도/매수
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pyupbit

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class EmergencyTrader:
    """긴급 거래 감지 및 실행"""

    def __init__(self):
        self.upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        
        # 급락/급등 임계값
        self.thresholds = {
            # 급락 기준 (매도) - 더 민감하게 조정 (2.5 -> 2.0, 4.0 -> 3.0)
            'crash_1min': -2.0,   # 1분 내 -2.0% 하락
            'crash_3min': -3.0,   # 3분 내 -3.0% 하락
            'crash_5min': -5.0,   # 5분 내 -5.0% 하락 (기존 -6.0)
            
            # 급등 기준 (매수)
            'surge_1min': 3.0,    # 1분 내 +3.0% 상승
            'surge_3min': 5.0,    # 3분 내 +5.0% 상승
            
            # 거래량 급증 (매수 시 필수)
            'volume_spike': 3.0,  # 평균 대비 3배
            
            # 변동성 급증 (추가 매도 신호)
            'volatility_spike': 2.0,  # 평균 변동성 2배
        }
        
        # 쿨다운: 동일 종목에 대해 5분 내 1회만 긴급 거래
        self.cooldown_minutes = 5
        self.last_emergency_trades: Dict[str, datetime] = {}
        
    def check_all_markets(self, positions: List[Dict], watch_markets: List[str]) -> Dict:
        """
        모든 관심 마켓 체크
        
        Args:
            positions: 현재 보유 포지션 [{market, amount, ...}, ...]
            watch_markets: 관심 마켓 리스트 ['KRW-BTC', 'KRW-ETH', ...]
            
        Returns:
            {
                'markets_checked': int,
                'emergency_actions': List[{market, action, reason, ...}],
                'results': List[{market, result, error, ...}]
            }
        """
        # 보유 포지션 마켓 추출
        position_markets = [p['market'] for p in positions] if positions else []
        
        # 중복 제거하고 전체 체크 대상 생성
        all_markets = list(set(position_markets + watch_markets))
        
        logger.info(f"Emergency check: {len(all_markets)} markets (positions: {len(position_markets)}, watch: {len(watch_markets)})")
        
        emergency_actions = []
        results = []
        
        for market in all_markets:
            try:
                # 쿨다운 체크
                if not self._can_trade(market):
                    continue
                
                # 긴급 신호 감지
                signal = self.detect_emergency_signal(market, is_holding=(market in position_markets))
                
                if signal:
                    action = signal['action']
                    reason = signal['reason']
                    
                    logger.warning(f"🚨 {market} 긴급 신호 감지: {action} - {reason}")
                    
                    emergency_actions.append({
                        'market': market,
                        'action': action,
                        'reason': reason,
                        'metrics': signal.get('metrics', {})
                    })
                    
                    # 거래 실행 (별도 메서드에서 처리)
                    # 실제 거래는 TradingEngine을 통해 수행되어야 함
                    result = {
                        'market': market,
                        'action': action,
                        'reason': reason,
                        'triggered': True
                    }
                    results.append(result)
                    
                    # 쿨다운 기록
                    self.last_emergency_trades[market] = datetime.now()
                    
            except Exception as e:
                logger.error(f"Error checking {market}: {e}")
                results.append({
                    'market': market,
                    'error': str(e),
                    'triggered': False
                })
        
        return {
            'markets_checked': len(all_markets),
            'emergency_actions': emergency_actions,
            'results': results
        }
    
    def detect_emergency_signal(self, market: str, is_holding: bool = False) -> Optional[Dict]:
        """
        단일 마켓의 긴급 신호 감지
        
        Args:
            market: 마켓 코드 (예: 'KRW-BTC')
            is_holding: 현재 보유 중인지 여부
            
        Returns:
            긴급 신호가 있으면 {action: 'emergency_sell'|'emergency_buy', reason: str, metrics: dict}
            없으면 None
        """
        try:
            # 1분, 3분, 5분 캔들 데이터 가져오기
            candles_1m = pyupbit.get_ohlcv(market, interval="minute1", count=5)
            candles_3m = pyupbit.get_ohlcv(market, interval="minute3", count=5)
            candles_5m = pyupbit.get_ohlcv(market, interval="minute5", count=5)
            
            if candles_1m is None or len(candles_1m) < 2:
                return None
            
            # 현재가
            current_price = candles_1m['close'].iloc[-1]
            
            # 가격 변화율 계산
            change_1m = ((current_price - candles_1m['close'].iloc[-2]) / candles_1m['close'].iloc[-2]) * 100
            change_3m = ((current_price - candles_3m['close'].iloc[-2]) / candles_3m['close'].iloc[-2]) * 100 if candles_3m is not None and len(candles_3m) >= 2 else 0
            change_5m = ((current_price - candles_5m['close'].iloc[-2]) / candles_5m['close'].iloc[-2]) * 100 if candles_5m is not None and len(candles_5m) >= 2 else 0
            
            # 거래량 비율 계산
            volume_current = candles_1m['volume'].iloc[-1]
            volume_avg = candles_1m['volume'].mean()
            volume_ratio = volume_current / volume_avg if volume_avg > 0 else 1
            
            # 변동성 계산 (ATR 개념)
            volatility_current = (candles_1m['high'].iloc[-1] - candles_1m['low'].iloc[-1]) / candles_1m['close'].iloc[-1] * 100
            volatility_avg = ((candles_1m['high'] - candles_1m['low']) / candles_1m['close']).mean() * 100
            
            metrics = {
                'change_1m': round(change_1m, 2),
                'change_3m': round(change_3m, 2),
                'change_5m': round(change_5m, 2),
                'volume_ratio': round(volume_ratio, 2),
                'volatility_current': round(volatility_current, 2),
                'volatility_avg': round(volatility_avg, 2),
            }
            
            logger.debug(f"{market} 긴급 체크 - 1분:{change_1m:.2f}%, 3분:{change_3m:.2f}%, 5분:{change_5m:.2f}%, 거래량:{volume_ratio:.2f}x, 변동성:{volatility_current:.2f}%")
            
            # 1. 급락 감지 (매도) - 보유 중일 때만
            if is_holding:
                if change_1m <= self.thresholds['crash_1min']:
                    return {
                        'action': 'emergency_sell',
                        'reason': f"1분 급락 감지 ({change_1m:.2f}%)",
                        'metrics': metrics
                    }
                
                if change_3m <= self.thresholds['crash_3min']:
                    return {
                        'action': 'emergency_sell',
                        'reason': f"3분 급락 감지 ({change_3m:.2f}%)",
                        'metrics': metrics
                    }
                
                if change_5m <= self.thresholds['crash_5min']:
                    return {
                        'action': 'emergency_sell',
                        'reason': f"5분 급락 감지 ({change_5m:.2f}%)",
                        'metrics': metrics
                    }
                
                # 변동성 급증 + 하락
                if volatility_current > volatility_avg * self.thresholds['volatility_spike'] and change_1m < 0:
                    return {
                        'action': 'emergency_sell',
                        'reason': f"변동성 급증 + 하락 (변동성 {volatility_current:.2f}%, 하락 {change_1m:.2f}%)",
                        'metrics': metrics
                    }
            
            # 2. 급등 감지 (매수) - 보유 중이 아닐 때만
            if not is_holding:
                if change_1m >= self.thresholds['surge_1min'] and volume_ratio >= self.thresholds['volume_spike']:
                    return {
                        'action': 'emergency_buy',
                        'reason': f"거래량 동반 급등 ({change_1m:.2f}%, {volume_ratio:.2f}x)",
                        'metrics': metrics
                    }
                
                if change_3m >= self.thresholds['surge_3min'] and volume_ratio >= self.thresholds['volume_spike']:
                    return {
                        'action': 'emergency_buy',
                        'reason': f"3분 거래량 동반 급등 ({change_3m:.2f}%, {volume_ratio:.2f}x)",
                        'metrics': metrics
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting emergency signal for {market}: {e}")
            return None
    
    def _can_trade(self, market: str) -> bool:
        """쿨다운 체크 - 마지막 거래 후 충분한 시간 경과했는지"""
        if market not in self.last_emergency_trades:
            return True
        
        last_trade = self.last_emergency_trades[market]
        elapsed = datetime.now() - last_trade
        
        if elapsed < timedelta(minutes=self.cooldown_minutes):
            remaining = timedelta(minutes=self.cooldown_minutes) - elapsed
            logger.debug(f"{market} 쿨다운 중 (남은 시간: {remaining.total_seconds():.0f}초)")
            return False
        
        return True
    
    def execute_emergency_trade(self, market: str, action: str, reason: str) -> Dict:
        """
        긴급 거래 실제 실행
        
        Args:
            market: 마켓 코드
            action: 'emergency_sell' 또는 'emergency_buy'
            reason: 거래 사유
            
        Returns:
            {success: bool, order_id: str, error: str}
        """
        try:
            if action == 'emergency_sell':
                # 전량 매도
                balance = self.upbit.get_balance(market.split('-')[1])
                balance_float = float(balance) if balance else 0.0
                
                if balance_float > 0:
                    logger.warning(f"💥 {market} 긴급 매도 실행! (사유: {reason})")
                    order = self.upbit.sell_market_order(market, balance_float)
                    order_id = order.get('uuid') if isinstance(order, dict) else None
                    return {
                        'success': True,
                        'order_id': order_id,
                        'amount': balance_float,
                        'action': action,
                        'reason': reason
                    }
                else:
                    return {'success': False, 'error': '보유 수량 없음'}
            
            elif action == 'emergency_buy':
                # 설정된 금액만큼 매수
                trade_amount = settings.default_trade_amount
                krw_balance = self.upbit.get_balance("KRW")
                krw_balance_float = float(krw_balance) if krw_balance else 0.0
                
                if krw_balance_float >= trade_amount:
                    logger.warning(f"🚀 {market} 긴급 매수 실행! (사유: {reason})")
                    order = self.upbit.buy_market_order(market, trade_amount)
                    order_id = order.get('uuid') if isinstance(order, dict) else None
                    return {
                        'success': True,
                        'order_id': order_id,
                        'amount': trade_amount,
                        'action': action,
                        'reason': reason
                    }
                else:
                    return {'success': False, 'error': 'KRW 잔액 부족'}
            
            return {'success': False, 'error': f'알 수 없는 액션: {action}'}
            
        except Exception as e:
            logger.error(f"Error executing emergency trade for {market}: {e}")
            return {'success': False, 'error': str(e)}


# 싱글톤 인스턴스
emergency_trader = EmergencyTrader()
