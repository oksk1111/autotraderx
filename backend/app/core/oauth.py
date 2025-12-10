"""
OAuth 클라이언트 (Google, Naver, Kakao)
"""
from authlib.integrations.httpx_client import AsyncOAuth2Client
from typing import Dict, Optional
import os
import httpx


class OAuthConfig:
    """OAuth 설정 (환경변수 기반)"""
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:4173/auth/google/callback")
    
    # Naver OAuth
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
    NAVER_REDIRECT_URI = os.getenv("NAVER_REDIRECT_URI", "http://localhost:4173/auth/naver/callback")
    
    # Kakao OAuth
    KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
    KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
    KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:4173/auth/kakao/callback")


class GoogleOAuthClient:
    """Google OAuth 클라이언트"""
    
    AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def __init__(self):
        if not OAuthConfig.GOOGLE_CLIENT_ID or not OAuthConfig.GOOGLE_CLIENT_SECRET:
            raise ValueError(
                "Google OAuth 설정이 필요합니다.\n"
                ".env 파일에 다음을 추가하세요:\n"
                "GOOGLE_CLIENT_ID=your_client_id\n"
                "GOOGLE_CLIENT_SECRET=your_client_secret\n"
                "GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback\n\n"
                "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하세요:\n"
                "https://console.cloud.google.com/apis/credentials"
            )
        
        self.client_id = OAuthConfig.GOOGLE_CLIENT_ID
        self.client_secret = OAuthConfig.GOOGLE_CLIENT_SECRET
        self.redirect_uri = OAuthConfig.GOOGLE_REDIRECT_URI
    
    def get_authorization_url(self, state: str = None) -> str:
        """인증 URL 생성"""
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="openid email profile"
        )
        url, _ = client.create_authorization_url(
            self.AUTHORIZATION_ENDPOINT,
            state=state
        )
        return url
    
    async def get_access_token(self, code: str) -> Dict:
        """인증 코드로 액세스 토큰 획득"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict:
        """사용자 정보 조회"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "oauth_id": data["id"],
                "email": data["email"],
                "name": data.get("name"),
                "profile_image": data.get("picture")
            }


class NaverOAuthClient:
    """Naver OAuth 클라이언트"""
    
    AUTHORIZATION_ENDPOINT = "https://nid.naver.com/oauth2.0/authorize"
    TOKEN_ENDPOINT = "https://nid.naver.com/oauth2.0/token"
    USERINFO_ENDPOINT = "https://openapi.naver.com/v1/nid/me"
    
    def __init__(self):
        if not OAuthConfig.NAVER_CLIENT_ID or not OAuthConfig.NAVER_CLIENT_SECRET:
            raise ValueError(
                "Naver OAuth 설정이 필요합니다.\n"
                ".env 파일에 다음을 추가하세요:\n"
                "NAVER_CLIENT_ID=your_client_id\n"
                "NAVER_CLIENT_SECRET=your_client_secret\n"
                "NAVER_REDIRECT_URI=http://localhost:3000/auth/naver/callback\n\n"
                "네이버 개발자센터에서 애플리케이션을 등록하세요:\n"
                "https://developers.naver.com/apps/#/register"
            )
        
        self.client_id = OAuthConfig.NAVER_CLIENT_ID
        self.client_secret = OAuthConfig.NAVER_CLIENT_SECRET
        self.redirect_uri = OAuthConfig.NAVER_REDIRECT_URI
    
    def get_authorization_url(self, state: str = None) -> str:
        """인증 URL 생성"""
        import urllib.parse
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state or "random_state"
        }
        return f"{self.AUTHORIZATION_ENDPOINT}?{urllib.parse.urlencode(params)}"
    
    async def get_access_token(self, code: str, state: str = None) -> Dict:
        """인증 코드로 액세스 토큰 획득"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "state": state or "random_state"
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict:
        """사용자 정보 조회"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            user_data = data["response"]
            return {
                "oauth_id": user_data["id"],
                "email": user_data["email"],
                "name": user_data.get("name"),
                "profile_image": user_data.get("profile_image")
            }


class KakaoOAuthClient:
    """Kakao OAuth 클라이언트"""
    
    AUTHORIZATION_ENDPOINT = "https://kauth.kakao.com/oauth/authorize"
    TOKEN_ENDPOINT = "https://kauth.kakao.com/oauth/token"
    USERINFO_ENDPOINT = "https://kapi.kakao.com/v2/user/me"
    
    def __init__(self):
        if not OAuthConfig.KAKAO_CLIENT_ID:
            raise ValueError(
                "Kakao OAuth 설정이 필요합니다.\n"
                ".env 파일에 다음을 추가하세요:\n"
                "KAKAO_CLIENT_ID=your_rest_api_key\n"
                "KAKAO_REDIRECT_URI=http://localhost:3000/auth/kakao/callback\n\n"
                "카카오 개발자센터에서 애플리케이션을 등록하세요:\n"
                "https://developers.kakao.com/console/app"
            )
        
        self.client_id = OAuthConfig.KAKAO_CLIENT_ID
        self.redirect_uri = OAuthConfig.KAKAO_REDIRECT_URI
    
    def get_authorization_url(self, state: str = None) -> str:
        """인증 URL 생성"""
        import urllib.parse
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri
        }
        return f"{self.AUTHORIZATION_ENDPOINT}?{urllib.parse.urlencode(params)}"
    
    async def get_access_token(self, code: str) -> Dict:
        """인증 코드로 액세스 토큰 획득"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_ENDPOINT,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "code": code
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict:
        """사용자 정보 조회"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            kakao_account = data.get("kakao_account", {})
            profile = kakao_account.get("profile", {})
            
            return {
                "oauth_id": str(data["id"]),
                "email": kakao_account.get("email"),
                "name": profile.get("nickname"),
                "profile_image": profile.get("profile_image_url")
            }


def get_oauth_client(provider: str):
    """OAuth 클라이언트 팩토리"""
    clients = {
        "google": GoogleOAuthClient,
        "naver": NaverOAuthClient,
        "kakao": KakaoOAuthClient
    }
    
    client_class = clients.get(provider.lower())
    if not client_class:
        raise ValueError(f"지원하지 않는 OAuth 제공자: {provider}")
    
    return client_class()
