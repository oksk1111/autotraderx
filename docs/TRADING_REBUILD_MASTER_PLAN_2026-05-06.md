# AutoTraderX 전면 개편 기획서 (2026-05-06)

## 1. 문제 진단
- 초기 자본 300,000 KRW -> 26,520 KRW로 약 91.16% 손실.
- 실패 핵심 원인:
  - 급등 구간 추격 진입(FOMO)으로 고점 체결 반복.
  - 다중 엔진/다중 전략이 중첩되어 책임 경로가 불명확함.
  - WebSocket 수신 코드는 있었으나, 실제 매매 의사결정은 폴링 의존이 큼.
  - 손실 제한은 존재했지만 진입 품질 관리(레짐 필터/진입 위치)가 약함.

## 2. 전면 개편 원칙
- 원칙 1: 자본 보존 우선 (survive first).
- 원칙 2: 급등 추격 매수 금지.
- 원칙 3: 상위 타임프레임 추세가 확인된 경우에만 진입.
- 원칙 4: 손실은 작게, 이익은 손익비로 관리.
- 원칙 5: 급등은 매수 신호가 아니라 경고 이벤트로 취급.

## 3. 신규 전략 구조 (Capital Preservation Strategy)
- 전략명: CapitalPreservationStrategy
- 진입(매수) 조건:
  - 1h, 15m 추세 필터 통과 (EMA20 > EMA50).
  - 5m에서 EMA20 근접 눌림 + RSI 46~62 + 거래량 확인.
  - 직전 급등 캔들(3~5봉 과열)에서는 진입 금지.
- 청산(매도) 조건:
  - 추세 붕괴 (1h/15m 동시 약화) 또는 5m 모멘텀 붕괴.
  - 별도 포지션 관리 로직의 Stop/Take/Trailing은 유지.
- 리스크:
  - 기본 손절 1.2%
  - 기본 익절 2.6%
  - 포지션 비중 6~14% (신뢰도 기반)

## 4. 실시간 급등 대응 방식
- 결론: "있다". Upbit는 WebSocket Ticker 스트림 제공.
- 적용 방식:
  - 급등 감지 루프를 WebSocket 기반으로 별도 실행.
  - 급등 조건 충족 시 즉시 Telegram/Slack 알림 전송.
  - 정책: alert-only (자동 추격 매수 금지).
- 임계값 기본값:
  - 20초 내 +1.8% 이상
  - 24h 거래대금 최소 350억 KRW
  - 동일 코인 재알림 쿨다운 180초

## 5. 구현 반영 파일
- 신규:
  - backend/app/trading/capital_preservation_strategy.py
  - docs/TRADING_REBUILD_MASTER_PLAN_2026-05-06.md
- 수정:
  - backend/app/tasks/trading.py
  - backend/app/core/config.py
  - backend/app/celery_app.py

## 6. 운영 절차
1. 기존 worker/beat 재시작으로 신규 스케줄 반영.
2. 첫 3일은 소액 모드(기본값 유지)로 실거래 검증.
3. 급등 알림 정확도(오탐/누락) 측정 후 threshold 미세 조정.
4. 7일 누적 손익/최대낙폭 기준으로 비중 재설정.

## 7. 즉시 적용 성공 기준
- 과열 구간 추격 매수 로그가 0건.
- 손절 평균 손실폭이 기존 대비 축소.
- 급등 이벤트가 WebSocket 기반으로 수 초 내 알림 도달.
- 일일 손실 한도 도달 시 신규 매수 0건.
