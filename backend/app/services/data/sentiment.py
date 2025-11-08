"""
실시간 뉴스 및 트렌드 데이터 수집기
"""
import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class NewsCollector:
    """뉴스 데이터 수집기"""
    
    def __init__(self):
        self.news_api_key = getattr(settings, 'NEWS_API_KEY', None)
        self.news_api_url = "https://newsapi.org/v2/everything"
    
    def get_crypto_news(
        self,
        keyword: str = "bitcoin cryptocurrency",
        language: str = "en",
        hours: int = 24
    ) -> List[Dict]:
        """암호화폐 관련 뉴스 수집"""
        
        if not self.news_api_key:
            logger.warning("NEWS_API_KEY가 설정되지 않았습니다.")
            return []
        
        try:
            from_date = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            params = {
                'q': keyword,
                'language': language,
                'from': from_date,
                'sortBy': 'publishedAt',
                'apiKey': self.news_api_key,
                'pageSize': 10
            }
            
            response = requests.get(self.news_api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                
                return [{
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'publishedAt': article.get('publishedAt', ''),
                    'source': article.get('source', {}).get('name', '')
                } for article in articles]
            else:
                logger.error(f"News API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return []
    
    def summarize_news(self, articles: List[Dict]) -> str:
        """뉴스 요약"""
        if not articles:
            return "최근 뉴스 없음"
        
        summary_parts = []
        for i, article in enumerate(articles[:5], 1):
            title = article.get('title', '')
            source = article.get('source', '')
            summary_parts.append(f"{i}. [{source}] {title}")
        
        return "\n".join(summary_parts)


class TrendCollector:
    """트렌드 데이터 수집기 (Google Trends 대체)"""
    
    def __init__(self):
        # Google Trends API는 공식 API가 없으므로 pytrends 라이브러리 사용
        # 또는 간단한 검색량 추정
        pass
    
    def get_trend_score(self, keyword: str = "bitcoin") -> float:
        """검색 트렌드 점수 추정 (0-100)"""
        try:
            # 실제 구현 시 pytrends 라이브러리 사용
            # 현재는 더미 데이터 반환
            logger.info(f"트렌드 점수 조회: {keyword}")
            
            # TODO: pytrends 구현
            # from pytrends.request import TrendReq
            # pytrends = TrendReq(hl='ko-KR', tz=540)
            # pytrends.build_payload([keyword], timeframe='now 1-d')
            # data = pytrends.interest_over_time()
            
            # 임시: 50-80 사이 랜덤 값
            import random
            return random.uniform(50, 80)
            
        except Exception as e:
            logger.error(f"Failed to get trend score: {e}")
            return 50.0


class MarketSentimentCollector:
    """시장 심리 데이터 수집기"""
    
    def __init__(self):
        self.news_collector = NewsCollector()
        self.trend_collector = TrendCollector()
    
    def collect_all(self, keyword: str = "bitcoin") -> Dict:
        """모든 감성 데이터 수집"""
        
        # 뉴스 수집
        news_articles = self.news_collector.get_crypto_news(keyword)
        news_summary = self.news_collector.summarize_news(news_articles)
        
        # 트렌드 수집
        trend_score = self.trend_collector.get_trend_score(keyword)
        
        # 간단한 감성 점수 계산
        sentiment_score = self._calculate_sentiment(news_articles)
        
        return {
            'news_articles': news_articles,
            'news_summary': news_summary,
            'trend_score': trend_score,
            'sentiment_score': sentiment_score,
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_sentiment(self, articles: List[Dict]) -> float:
        """뉴스 감성 분석 (간단한 키워드 기반)"""
        if not articles:
            return 50.0
        
        positive_keywords = [
            'surge', 'rally', 'gain', 'rise', 'bullish', 'profit',
            '상승', '급등', '호재', '긍정'
        ]
        negative_keywords = [
            'crash', 'fall', 'drop', 'bearish', 'loss', 'decline',
            '하락', '급락', '악재', '부정'
        ]
        
        positive_count = 0
        negative_count = 0
        
        for article in articles:
            text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            
            for keyword in positive_keywords:
                if keyword in text:
                    positive_count += 1
            
            for keyword in negative_keywords:
                if keyword in text:
                    negative_count += 1
        
        total = positive_count + negative_count
        if total == 0:
            return 50.0
        
        sentiment = (positive_count / total) * 100
        return sentiment


# Singleton instance
market_sentiment = MarketSentimentCollector()
