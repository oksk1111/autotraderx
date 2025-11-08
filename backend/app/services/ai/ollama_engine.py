"""
Ollama 기반 AI 트레이딩 판단 엔진
DeepSeek-R1 모델을 활용한 실시간 매매 의사결정
"""
import requests
import logging
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaEngine:
    """Ollama LLM 기반 트레이딩 AI 엔진"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434')
        self.model = getattr(settings, 'OLLAMA_MODEL', 'deepseek-r1:8b')
        self.temperature = getattr(settings, 'OLLAMA_TEMPERATURE', 0.7)
        
    def get_available_models(self) -> List[Dict]:
        """Ollama에 설치된 모델 목록 조회"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                return [
                    {
                        'name': model.get('name'),
                        'size': model.get('size', 0),
                        'modified_at': model.get('modified_at'),
                        'digest': model.get('digest', '')[:12]  # 짧게 표시
                    }
                    for model in models
                ]
            else:
                logger.error(f"Failed to get models: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting models: {e}")
            return []
    
    def set_model(self, model_name: str) -> bool:
        """사용할 모델 변경"""
        try:
            # 모델이 존재하는지 확인
            available_models = self.get_available_models()
            model_names = [m['name'] for m in available_models]
            
            if model_name not in model_names:
                logger.error(f"Model {model_name} not found. Available: {model_names}")
                return False
            
            self.model = model_name
            logger.info(f"Model changed to: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting model: {e}")
            return False
    
    def pull_model(self, model_name: str) -> Dict:
        """Ollama 모델 다운로드"""
        try:
            logger.info(f"Pulling model: {model_name}")
            
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=600,  # 10분 타임아웃
                stream=True
            )
            
            if response.status_code == 200:
                # 스트림 응답 처리
                for line in response.iter_lines():
                    if line:
                        # 진행 상황 로깅
                        logger.info(line.decode('utf-8'))
                
                return {"success": True, "message": f"Model {model_name} downloaded"}
            else:
                return {"success": False, "message": f"Failed to pull model: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            return {"success": False, "message": str(e)}
        
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Ollama API 호출"""
        try:
            logger.info(f"Calling Ollama API with model: {self.model}")
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": self.temperature
                },
                timeout=180  # 3분으로 증가 (DeepSeek-R1 모델은 추론이 느림)
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                logger.info(f"Ollama 응답 받음: {len(response_text)} 글자")
                return response_text
            else:
                logger.error(f"Ollama API error: {response.status_code}, {response.text}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ollama 서버에 연결할 수 없습니다: {e}")
            return None
        except requests.exceptions.Timeout as e:
            logger.error(f"Ollama API 타임아웃: {e}")
            return None
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            return None
    
    def generate_trading_prompt(
        self,
        market_data: Dict,
        indicators: Dict,
        news_summary: Optional[str] = None,
        trend_score: Optional[float] = None
    ) -> str:
        """트레이딩 판단을 위한 프롬프트 생성"""
        
        current_price = market_data.get('trade_price', 0)
        volume_24h = market_data.get('acc_trade_volume_24h', 0)
        change_rate = market_data.get('signed_change_rate', 0) * 100
        
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {})
        ma_5 = indicators.get('ma_5', 0)
        ma_20 = indicators.get('ma_20', 0)
        mfi = indicators.get('mfi', 50)
        trend = indicators.get('trend', 'neutral')
        
        prompt = f"""당신은 암호화폐 단기 트레이딩 전문가입니다. 다음 시장 데이터를 분석하여 매매 결정을 내려주세요.

## 📊 현재 시장 상황
- 현재가: {current_price:,.0f}원
- 24시간 거래량: {volume_24h:,.2f}
- 등락률: {change_rate:+.2f}%

## 📈 기술적 지표
- RSI: {rsi:.2f} (30 이하: 과매도, 70 이상: 과매수)
- MACD: {macd.get('macd', 0):.2f}, Signal: {macd.get('signal', 0):.2f}, Histogram: {macd.get('histogram', 0):.2f}
- 5일 이동평균: {ma_5:,.0f}원
- 20일 이동평균: {ma_20:,.0f}원
- MFI (자금흐름): {mfi:.2f}
- 추세: {trend}

"""
        
        if news_summary:
            prompt += f"""## 📰 최근 뉴스 요약
{news_summary}

"""
        
        if trend_score:
            prompt += f"""## 🔥 검색 트렌드 점수
{trend_score}/100 (관심도 지표)

"""
        
        prompt += """## 🎯 매매 판단 기준
1. **워뇨띠식 단기 트레이딩 원칙**
   - 급상승 패턴 포착 시 진입
   - 패턴 이탈 즉시 매도
   - 손절: -1.5%, 익절: +2.5%

2. **기술적 분석**
   - RSI + MACD 동시 고려
   - 거래량 급증 여부
   - 이동평균선 배열

3. **리스크 관리**
   - 과매수/과매도 구간 회피
   - 추세 전환 시그널 중요도 높음

## 📝 결정 출력 형식
다음 중 **정확히 하나만** 선택하여 출력하세요:
- 매수 (이유: 구체적인 근거)
- 매도 (이유: 구체적인 근거)
- 유지 (이유: 구체적인 근거)

**결정:**
"""
        
        return prompt
    
    def analyze_and_decide(
        self,
        market_data: Dict,
        indicators: Dict,
        news_summary: Optional[str] = None,
        trend_score: Optional[float] = None
    ) -> Dict:
        """AI 기반 매매 의사결정"""
        
        # 프롬프트 생성
        prompt = self.generate_trading_prompt(
            market_data, indicators, news_summary, trend_score
        )
        
        # Ollama 호출
        response = self._call_ollama(prompt)
        
        if not response:
            logger.warning("Ollama 응답 없음 - 기본 전략으로 폴백")
            return self._fallback_decision(indicators)
        
        # 응답 파싱
        decision = self._parse_decision(response)
        
        logger.info(f"AI 판단: {decision['action']} - {decision['reason']}")
        
        return decision
    
    def _parse_decision(self, response: str) -> Dict:
        """Ollama 응답 파싱"""
        response_lower = response.lower()
        
        # 매수/매도/유지 키워드 검색
        if '매수' in response or 'buy' in response_lower:
            action = 'buy'
            confidence = 0.8
        elif '매도' in response or 'sell' in response_lower:
            action = 'sell'
            confidence = 0.8
        else:
            action = 'hold'
            confidence = 0.6
        
        # 이유 추출 (간단한 방식)
        reason = response.replace('\n', ' ').strip()[:200]
        
        return {
            'action': action,
            'confidence': confidence,
            'reason': reason,
            'raw_response': response
        }
    
    def _fallback_decision(self, indicators: Dict) -> Dict:
        """Ollama 실패 시 기본 전략"""
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {})
        
        if rsi < 30 and macd.get('histogram', 0) > 0:
            return {
                'action': 'buy',
                'confidence': 0.6,
                'reason': 'Fallback: RSI oversold + MACD positive'
            }
        elif rsi > 70 and macd.get('histogram', 0) < 0:
            return {
                'action': 'sell',
                'confidence': 0.6,
                'reason': 'Fallback: RSI overbought + MACD negative'
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'reason': 'Fallback: No clear signal'
            }
    
    def check_health(self) -> bool:
        """Ollama 서버 상태 확인"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


# Singleton instance
ollama_engine = OllamaEngine()
