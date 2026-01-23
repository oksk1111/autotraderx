# 투자 원칙 및 전략 가이드 (Investment Principles & Strategy)

> **Rule No.1: Never Lose Money (돈을 잃지 마라)**
> **Rule No.2: Never Forget Rule No.1 (제1원칙을 절대 잊지 마라)**
> - Warren Buffett

이 문서는 시스템의 양대 축인 **워렌 버핏의 가치 검증**과 **워뇨띠의 기계적 대응**을 기술적으로 융합한 5.0 가이드라인입니다.

## 1. 핵심 철학: Hybrid Strategy (5.0 Implementation)

### A. Warren Buffett Mode (건강한 자산 선정)
*   **원칙:** "모르는 것, 위험한 것에는 손대지 않는다."
*   **Scam Filtering (스캠 원천 차단):**
    *   **유의 종목(Caution):** 거래소가 지정한 유의/주의 종목은 매수 대상 후보군 생성 단계에서 **즉시 탈락**시킵니다.
    *   **유동성 검증:** 24시간 거래대금 최상위권(Top 10~20) 코인만 다룹니다. 거래량이 죽은 코인은 지표가 좋아도 매수하지 않습니다.
    *   **건강한 추세:** 일시적 펌핑이 아닌, 꾸준한 거래량과 추세를 동반한 'Trendy'한 자산만 매수합니다.

### B. Wonyyotti (aoa) Mode (기계적 리스크 관리)
*   **원칙:** "시장은 예측의 영역이 아니라 대응의 영역이다."
*   **상시 추세 점검 (Continuous Trend Review):**
    *   매수 이후 '존버'는 없습니다. **모든 보유 포지션**은 매 1분마다 원점에서 재평가(Re-evaluation)됩니다.
    *   질문: *"현금을 들고 있다면 지금 이 가격에 다시 매수하겠는가?"* 
        *   YES (Strong Buy) -> **HOLD**
        *   NO (Weak/Sell) -> **EXIT** (이미 손실 중이라면 즉시 손절)
*   **칼 같은 손절 (Razor-sharp Stop Loss):**
    *   **Hard Stop:** -4% 도달 시 어떤 기술적 지표도 무시하고 무조건 시장가 청산.
    *   **Trailing Stop:** 수익이 나면 익절 라인을 계속 올리며 수익을 끝까지 추적하되, 반전 시 바로 확정.

## 2. 기술적 구현 (Technical Implementation)

### A. 시스템 보호 장치 (Safety Nets)
1.  **Investment Warning Check:**
    *   Upbit API의 `market_warning` 필드를 조회하여 'CAUTION' 상태인 코인은 매수 목록에서 제외합니다.
2.  **Double Stop Loss Logic:**
    *   Soft Stop: 진입가 대비 -2% (일반적 손절)
    *   **Hard Stop:** -4% (시스템 오류나 급락 대비 절대 마지노선, 강제 청산)
3.  **Active Trend enforcement:**
    *   손실 중(-3% 이상)인 포지션은 추세가 '강력한 매수(Confidence > 0.7)' 상태가 아니면 매도하여 리스크를 제거합니다.

### B. AI 기반 진입 필터 (AI Entry Filter)
*   **High Probability:** 머신러닝 모델의 승률 예측이 높고, LLM(Groq/Ollama)이 시장 상황을 긍정적으로 평가할 때만 진입합니다.

## 3. 운영 가이드 (Operation Guide)

### 투자자가 할 일
1.  **Rule No.1 상기:** 봇이 "NO TRADE" 상태로 오래 쉬더라도 조바심 내지 마십시오. 돈을 잃지 않는 것이 버는 것입니다.
2.  **모니터링:** 봇이 설정한 Trailing Stop이 잘 따라가고 있는지 로그(`logs/`)를 통해 확인하십시오.

### 시스템 개선 로드맵
- [x] Market Selector에 유의종목(Caution) 필터링 추가
- [x] 보유 종목 상시 추세 점검(Trend Review) 로직 강화
- [x] 절대 손절 라인(Hard Stop Limit) 구현
- [ ] 펌핑 감지(Pump Detection) 알고리즘 고도화

---
*Last Updated: 2026-01-24*
