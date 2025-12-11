#!/usr/bin/env python3
"""
Daily Health Check Script
매일 시스템 상태를 점검하고 Groq LLM으로 분석 결과를 생성합니다.
"""
import os
import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models.trading import AutoTradingConfig, TradePosition
from app.llm.groq_client import GroqClient
from app.core.config import get_settings
from app.services.notifications import Notifier
import json
import pyupbit


def get_system_health() -> dict:
    """시스템 상태 정보 수집"""
    db = SessionLocal()
    
    try:
        # 1. 설정 정보
        config = db.query(AutoTradingConfig).first()
        
        # 2. 포지션 정보
        total_positions = db.query(TradePosition).count()
        open_positions = db.query(TradePosition).filter(
            TradePosition.status == "OPEN"
        ).all()
        
        # 3. 최근 24시간 포지션 히스토리
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_positions = db.query(TradePosition).filter(
            TradePosition.created_at >= yesterday
        ).all()
        
        # 4. 미실현 PnL 계산 (Open Position)
        unrealized_pnl = 0.0
        total_asset_value = 0.0
        
        try:
            for pos in open_positions:
                current_price = pyupbit.get_current_price(pos.market)
                if current_price:
                    current_val = pos.size * float(current_price)
                    entry_val = pos.size * pos.entry_price
                    unrealized_pnl += (current_val - entry_val)
                    total_asset_value += current_val
        except Exception as e:
            print(f"⚠️ PnL 계산 중 오류: {e}")
        
        # 5. 시스템 상태 (간단하게)
        container_status = {
            "note": "Container status check skipped (requires Docker socket access)"
        }
        
        # 6. 에러 카운트 (간략화)
        error_count = 0
        recent_errors = []
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "config": {
                "is_active": config.is_active if config else False,
                "selected_markets": config.selected_markets if config else [],
                "use_ai": config.use_ai if config else False,
                "min_confidence": config.min_confidence if config else 0.0,
                "trading_cycle_seconds": config.trading_cycle_seconds if config else 0,
            },
            "positions": {
                "total": total_positions,
                "open": len(open_positions),
                "recent_24h_count": len(recent_positions),
            },
            "performance": {
                "unrealized_pnl": float(unrealized_pnl),
                "total_asset_value": float(total_asset_value),
                "open_position_count": len(open_positions)
            },
            "containers": container_status,
            "errors": {
                "count": error_count,
                "recent": recent_errors
            }
        }
    finally:
        db.close()


async def analyze_with_groq(health_data: dict) -> str:
    """Groq LLM으로 헬스 데이터 분석"""
    
    # Groq API 키 확인
    settings = get_settings()
    
    if not settings.groq_api_key:
        return "⚠️ GROQ_API_KEY가 설정되지 않았습니다. LLM 분석을 건너뜁니다."
    
    try:
        client = GroqClient(settings)
        
        messages = [
            {
                "role": "system",
                "content": "당신은 암호화폐 자동매매 시스템의 수석 운영자입니다. 시스템 상태 데이터를 분석하여 명확하고 통찰력 있는 일일 리포트를 작성하세요."
            },
            {
                "role": "user",
                "content": f"""
다음 시스템 상태 데이터를 분석하고, 한국어로 일일 리포트를 작성해주세요.

시스템 상태:
{json.dumps(health_data, indent=2, ensure_ascii=False)}

다음 항목을 포함해주세요:
1. 🚦 시스템 상태 요약 (정상/주의/경고) - 한 줄 요약
2. 💰 거래 성과 분석 (PnL, 거래량, 승률 등)
3. ⚙️ 시스템 운영 현황 (설정, 포지션 상태)
4. 🛡️ 리스크 및 제언 (발견된 문제점이나 개선 제안)

이모지를 적절히 사용하여 가독성을 높여주세요.
"""
            }
        ]

        if hasattr(client, 'chat'):
            content = await client.chat(messages)
        else:
            # Fallback if chat method is not available (should not happen if edit succeeded)
            response_data = await client.verify(messages[1]["content"])
            content = response_data["choices"][0]["message"]["content"]
        
        return content
        
    except Exception as e:
        return f"⚠️ LLM 분석 실패: {str(e)}\n\n원본 데이터:\n{json.dumps(health_data, indent=2, ensure_ascii=False)}"


async def send_notification(report: str):
    """알림 전송 (Slack, Telegram)"""
    
    # 콘솔 출력
    print("=" * 80)
    print("🏥 일일 헬스 체크 리포트")
    print("=" * 80)
    print(report)
    print("=" * 80)
    
    notifier = Notifier()
    await notifier.send("🏥 AutoTraderX 일일 리포트", report)
    print("✅ 알림 전송 요청 완료")


async def main():
    """메인 실행 함수"""
    print(f"🏥 일일 헬스 체크 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 시스템 상태 수집
    print("📊 시스템 상태 수집 중...")
    health_data = get_system_health()
    
    # 2. Groq LLM 분석
    print("🤖 Groq LLM 분석 중...")
    report = await analyze_with_groq(health_data)
    
    # 3. 알림 전송
    print("📤 알림 전송 중...")
    await send_notification(report)
    
    print("✅ 일일 헬스 체크 완료")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


