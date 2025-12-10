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
import json


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
        ).count()
        
        # 3. 최근 24시간 포지션 히스토리
        yesterday = datetime.utcnow() - timedelta(hours=24)
        recent_positions = db.query(TradePosition).filter(
            TradePosition.created_at >= yesterday
        ).all()
        
        # 4. 시스템 상태 (간단하게)
        container_status = {
            "note": "Container status check skipped (requires Docker socket access)"
        }
        
        # 5. 에러 카운트 (간략화)
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
                "open": open_positions,
                "recent_24h": len(recent_positions),
                "recent_trades": [
                    {
                        "market": p.market,
                        "size": float(p.size),
                        "entry_price": float(p.entry_price),
                        "stop_loss": float(p.stop_loss),
                        "take_profit": float(p.take_profit),
                        "status": p.status,
                        "created_at": p.created_at.isoformat()
                    }
                    for p in recent_positions[:10]
                ]
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
        
        prompt = f"""당신은 자동매매 시스템 모니터링 전문가입니다.
아래 시스템 상태 데이터를 분석하고, 한국어로 간결한 일일 리포트를 작성해주세요.

시스템 상태:
{json.dumps(health_data, indent=2, ensure_ascii=False)}

다음 항목을 포함해주세요:
1. 시스템 상태 요약 (정상/주의/경고)
2. 거래 활동 분석 (24시간 기준)
3. 발견된 문제점 (있다면)
4. 권장 조치사항 (필요시)

이모지를 사용해서 가독성 좋게 작성해주세요."""

        response_data = await client.verify(prompt)
        content = response_data["choices"][0]["message"]["content"]
        
        return content
        
    except Exception as e:
        return f"⚠️ LLM 분석 실패: {str(e)}\n\n원본 데이터:\n{json.dumps(health_data, indent=2, ensure_ascii=False)}"


def send_notification(report: str):
    """알림 전송 (Slack, Email 등)"""
    
    # 콘솔 출력
    print("=" * 80)
    print("🏥 일일 헬스 체크 리포트")
    print("=" * 80)
    print(report)
    print("=" * 80)
    
    # TODO: Slack webhook 또는 이메일 전송 추가
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    if slack_webhook:
        import requests
        try:
            requests.post(slack_webhook, json={
                "text": f"🏥 AutoTraderX 일일 리포트\n\n{report}"
            })
            print("✅ Slack 알림 전송 완료")
        except Exception as e:
            print(f"⚠️ Slack 알림 전송 실패: {e}")


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
    send_notification(report)
    
    print("✅ 일일 헬스 체크 완료")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

