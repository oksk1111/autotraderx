#!/usr/bin/env python3
"""
Phase A 초기 설정 스크립트
- 암호화 키 생성
- JWT 비밀키 생성
- 환경변수 안내
"""
import sys
import os

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.encryption import generate_encryption_key
from app.core.jwt import generate_jwt_secret


def main():
    print("=" * 70)
    print(" Phase A 인증 시스템 초기 설정")
    print("=" * 70)
    print()
    
    # 1. 암호화 키 생성
    encryption_key = generate_encryption_key()
    print("1. Upbit API 키 암호화 키 (Fernet):")
    print(f"   ENCRYPTION_KEY={encryption_key}")
    print()
    
    # 2. JWT 비밀키 생성
    jwt_secret = generate_jwt_secret()
    print("2. JWT 서명 비밀키:")
    print(f"   JWT_SECRET_KEY={jwt_secret}")
    print()
    
    print("=" * 70)
    print(" 다음 단계:")
    print("=" * 70)
    print()
    print("1. .env 파일에 위 값들을 추가하세요:")
    print("   $ nano .env")
    print()
    print("2. OAuth 클라이언트 ID/Secret을 추가하세요:")
    print("   - Google: https://console.cloud.google.com/apis/credentials")
    print("   - Naver: https://developers.naver.com/apps/#/register")
    print("   - Kakao: https://developers.kakao.com/console/app")
    print()
    print("3. 데이터베이스 마이그레이션을 실행하세요:")
    print("   $ docker compose exec backend alembic upgrade head")
    print()
    print("4. 서버를 재시작하세요:")
    print("   $ docker compose restart backend")
    print()
    print("자세한 가이드: docs/PHASE_A_SETUP_GUIDE.md")
    print()


if __name__ == "__main__":
    main()
