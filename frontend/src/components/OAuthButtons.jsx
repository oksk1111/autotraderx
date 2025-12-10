/**
 * OAuth 로그인 버튼 컴포넌트
 * Google, Naver, Kakao 로그인 지원
 */
import React from 'react';

const OAuthButtons = () => {
  const handleOAuthLogin = async (provider) => {
    try {
      // 1. OAuth 인증 URL 요청
      const response = await fetch(`http://localhost:8000/api/auth/oauth/${provider}/url`);
      const data = await response.json();
      
      // 2. OAuth 제공자 로그인 페이지로 리디렉션
      window.location.href = data.authorization_url;
    } catch (error) {
      console.error(`${provider} 로그인 오류:`, error);
      alert('로그인에 실패했습니다. 다시 시도해주세요.');
    }
  };

  return (
    <div className="oauth-buttons">
      <h2>로그인</h2>
      
      <button
        onClick={() => handleOAuthLogin('google')}
        className="oauth-button google"
      >
        <img src="/icons/google.svg" alt="Google" />
        Google로 로그인
      </button>
      
      <button
        onClick={() => handleOAuthLogin('naver')}
        className="oauth-button naver"
      >
        <img src="/icons/naver.svg" alt="Naver" />
        네이버로 로그인
      </button>
      
      <button
        onClick={() => handleOAuthLogin('kakao')}
        className="oauth-button kakao"
      >
        <img src="/icons/kakao.svg" alt="Kakao" />
        카카오로 로그인
      </button>

      <style jsx>{`
        .oauth-buttons {
          max-width: 400px;
          margin: 50px auto;
          padding: 30px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        h2 {
          text-align: center;
          margin-bottom: 30px;
          color: #333;
        }

        .oauth-button {
          width: 100%;
          padding: 14px 20px;
          margin-bottom: 12px;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          transition: all 0.2s;
        }

        .oauth-button img {
          width: 20px;
          height: 20px;
        }

        .oauth-button:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .oauth-button.google {
          background: white;
          color: #333;
          border: 1px solid #ddd;
        }

        .oauth-button.naver {
          background: #03c75a;
          color: white;
        }

        .oauth-button.kakao {
          background: #fee500;
          color: #000;
        }
      `}</style>
    </div>
  );
};

export default OAuthButtons;
