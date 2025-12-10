/**
 * OAuth 콜백 처리 페이지
 * OAuth 제공자로부터 리디렉션되어 인증 코드를 받아 JWT 토큰으로 교환
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

const OAuthCallback = () => {
  const navigate = useNavigate();
  const { provider } = useParams(); // google, naver, kakao
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('처리 중...');

  useEffect(() => {
    handleCallback();
  }, []);

  const handleCallback = async () => {
    try {
      // URL에서 인증 코드 추출
      const code = searchParams.get('code');
      const state = searchParams.get('state');

      if (!code) {
        throw new Error('인증 코드가 없습니다.');
      }

      setStatus('로그인 처리 중...');

      // 백엔드로 인증 코드 전송
      const response = await fetch(
        `http://localhost:8000/api/auth/oauth/${provider}/callback`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ code, state }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '로그인에 실패했습니다.');
      }

      const data = await response.json();

      // JWT 토큰 저장
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      setStatus('로그인 성공! 리디렉션 중...');

      // 메인 페이지로 이동
      setTimeout(() => {
        navigate('/dashboard');
      }, 1000);

    } catch (error) {
      console.error('OAuth 콜백 오류:', error);
      setStatus(`오류: ${error.message}`);
      
      // 3초 후 로그인 페이지로 리디렉션
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    }
  };

  return (
    <div className="callback-container">
      <div className="spinner"></div>
      <p>{status}</p>

      <style jsx>{`
        .callback-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background: #f5f5f5;
        }

        .spinner {
          width: 50px;
          height: 50px;
          border: 4px solid #f3f3f3;
          border-top: 4px solid #3498db;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin-bottom: 20px;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        p {
          font-size: 18px;
          color: #333;
        }
      `}</style>
    </div>
  );
};

export default OAuthCallback;
