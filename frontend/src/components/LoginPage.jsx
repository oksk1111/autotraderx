/**
 * 로그인 페이지 컴포넌트
 * OAuth 로그인 UI 제공
 */
import React from 'react';
import '../styles/LoginPage.css';
import API_BASE_URL from '../config';

const LoginPage = () => {
  const handleOAuthLogin = async (provider) => {
    try {
      // 1. 백엔드에서 OAuth 인증 URL 요청
      const response = await fetch(`${API_BASE_URL}/api/auth/oauth/${provider}/url`);
      
      if (!response.ok) {
        throw new Error('OAuth URL 생성 실패');
      }
      
      const data = await response.json();
      
      // 2. OAuth 제공자 로그인 페이지로 리디렉션
      window.location.href = data.authorization_url;
    } catch (error) {
      console.error(`${provider} 로그인 오류:`, error);
      alert('로그인에 실패했습니다. 다시 시도해주세요.');
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-header">
          <h1>🤖 AutoTraderX</h1>
          <p>AI 기반 가상화폐 자동매매 시스템</p>
        </div>

        <div className="login-content">
          <h2>로그인</h2>
          <p className="login-description">
            소셜 계정으로 간편하게 로그인하세요
          </p>

          <div className="oauth-buttons">
            {/* Google 로그인 */}
            <button
              onClick={() => handleOAuthLogin('google')}
              className="oauth-button google"
            >
              <svg className="oauth-icon" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span>Google로 로그인</span>
            </button>

            {/* Naver 로그인 */}
            <button
              onClick={() => handleOAuthLogin('naver')}
              className="oauth-button naver"
            >
              <svg className="oauth-icon" viewBox="0 0 24 24">
                <rect fill="#03C75A" width="24" height="24" rx="4"/>
                <path fill="white" d="M16.273 12.845L7.376 0H0v24h7.726V11.156L16.624 24H24V0h-7.727v12.845z"/>
              </svg>
              <span>네이버로 로그인</span>
            </button>

            {/* Kakao 로그인 */}
            <button
              onClick={() => handleOAuthLogin('kakao')}
              className="oauth-button kakao"
            >
              <svg className="oauth-icon" viewBox="0 0 24 24">
                <path fill="#000000" d="M12 3c5.799 0 10.5 3.664 10.5 8.185 0 4.52-4.701 8.184-10.5 8.184a13.5 13.5 0 0 1-1.727-.11l-4.408 2.883c-.501.265-.678.236-.472-.413l.892-3.678c-2.88-1.46-4.785-3.99-4.785-6.866C1.5 6.665 6.201 3 12 3zm5.907 8.06l1.47-1.424a.472.472 0 0 0-.656-.678l-1.928 1.866V9.282a.472.472 0 0 0-.944 0v2.557a.471.471 0 0 0 0 .222V13.5a.472.472 0 0 0 .944 0v-1.363l.427-.413 1.428 2.033a.472.472 0 1 0 .773-.543l-1.514-2.155zm-2.958 1.924h-1.46V9.297a.472.472 0 0 0-.943 0v4.159c0 .26.21.472.471.472h1.932a.472.472 0 1 0 0-.944zm-5.857-1.092l.696-1.707.638 1.707H9.092zm2.523.488l.002-.016a.469.469 0 0 0-.127-.32l-1.046-2.8a.69.69 0 0 0-.627-.474.696.696 0 0 0-.653.447l-1.661 4.075a.472.472 0 0 0 .874.357l.33-.813h2.07l.299.8a.472.472 0 1 0 .884-.33l-.345-.926zM8.293 9.302a.472.472 0 0 0-.471-.472H4.577a.472.472 0 1 0 0 .944h1.16v3.736a.472.472 0 0 0 .944 0V9.774h1.14c.261 0 .472-.212.472-.472z"/>
              </svg>
              <span>카카오로 로그인</span>
            </button>
          </div>

          <div className="login-footer">
            <p className="terms-text">
              로그인 시 <a href="/terms">이용약관</a> 및 <a href="/privacy">개인정보처리방침</a>에 동의하게 됩니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
