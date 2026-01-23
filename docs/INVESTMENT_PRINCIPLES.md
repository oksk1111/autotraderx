# 투자 원칙 및 전략 가이드 (Investment Principles & Strategy)

> **Rule No.1: Never Lose Money (돈을 잃지 마라)**
> **Rule No.2: Never Forget Rule No.1 (제1원칙을 절대 잊지 마라)**
> - Warren Buffett

이 문서는 위 두 가지 대원칙을 시스템에 어떻게 적용하고, 수익을 극대화하면서 리스크를 최소화하지 설명합니다.

## 1. 핵심 철학 (Core Philosophy)

### "이기는 싸움만 한다"
- **보수적 진입:** 확신이 없을 때는 진입하지 않는다. (High Confidence Only)
- **빠른 손절:** 진입 판단이 틀렸다면 미련 없이 자른다. (Cut Losers Short)
- **수익 보존:** 한 번 수익이 난 포지션은 절대 손실로 마감하지 않는다. (Let Winners Run, but Lock in Profits)

## 2. 기술적 구현 (Technical Implementation)

### A. Trailing Stop (추적 손절매) - *Implemented*
수익을 극대화하면서도 하락 반전 시 이익을 지키기 위한 핵심 메커니즘입니다.

*   **작동 방식:** 가격이 상승함에 따라 Stop Loss(손절가) 라인을 같이 위로 끌어올립니다.
*   **로직:**
    *   현재가가 진입가 대비 **+2%** 이상 상승하면 활성화됩니다.
    *   새로운 Stop Loss = `MAX(현재가 - 2%, 본전가 + 수수료)`
    *   가격이 계속 오르면 Stop Loss도 계속 올라가 수익을 쫓아갑니다(Trailing).
    *   가격이 고점 대비 2% 하락하면 즉시 매도하여 수익을 확정합니다.
*   **효과:** "어깨에서 파는" 것을 자동화하여, 급등 후 급락하는 차트에서 수익을 반납하는 것을 방지합니다.

### B. Smart Risk Management (지능형 위험 관리) - *Implemented*
*   **본전 방어 (Break Even Mode):**
    *   수익이 조금이라도 나기 시작하면 Stop Loss를 `진입가 + 0.2%` (수수료 커버)로 이동시켜, 최악의 경우에도 수수료만 내고 원금은 지킵니다.
*   **유동적 손절 (Dynamic Stop Loss):**
    *   기존의 고정 -3% 손절 외에, 추세가 꺾이면 AI 판단 하에 즉시 매도합니다.
    *   이미 손실 중인 보유 종목(-10% 등)을 봇이 인계받을 경우, 무조건 즉시 파는 것이 아니라 **'현재가 -3%'**로 손절라인을 재설정하여 반등 기회를 주되 추가 폭락은 방어합니다.

### C. AI 기반 진입 필터 (AI Entry Filter)
*   **High Probability:** 머신러닝 모델의 승률 예측이 높고, LLM(Groq/Ollama)이 시장 상황을 긍정적으로 평가할 때만 진입합니다.

## 3. 운영 가이드 (Operation Guide)

### 투자자가 할 일
1.  **Rule No.1 상기:** 봇이 "NO TRADE" 상태로 오래 쉬더라도 조바심 내지 마십시오. 돈을 잃지 않는 것이 버는 것입니다.
2.  **모니터링:** 봇이 설정한 Trailing Stop이 잘 따라가고 있는지 로그(`logs/`)를 통해 확인하십시오.

### 시스템 개선 로드맵
- [x] 보유 종목 강제 분석 및 동기화 (Sync Holdings)
- [x] Trailing Stop 로직 적용
- [ ] 변동성 돌파 전략(VFI) 파라미터 최적화
- [ ] 하락장 전용 숏(Short) 대용 전략 (현물 매도 후 저점 재매수)

---
*작성일: 2026-01-23*
*작성자: GitHub Copilot*
