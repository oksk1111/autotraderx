/**
 * OAuth 콜백 처리 컴포넌트
 * OAuth 제공자로부터 리디렉션 받아서 토큰 교환
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import '../styles/AuthCallback.css';
import API_BASE_URL from '../config';

const AuthCallback = () => {
  const navigate = useNavigate();
  const { provider } = useParams();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('loading'); // loading, success, error
  const [message, setMessage] = useState('로그인 처리중...');

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // 1. URL에서 인증 코드 추출
        const code = searchParams.get('code');
        const error = searchParams.get('error');

        if (error) {
          throw new Error(`OAuth 오류: ${error}`);
        }

        if (!code) {
          throw new Error('인증 코드가 없습니다.');
        }

        console.log('OAuth 콜백 처리 시작:', { provider, code: code.substring(0, 10) + '...' });

        // 2. 백엔드로 인증 코드 전송하여 토큰 교환
        const response = await fetch(
          `${API_BASE_URL}/api/auth/oauth/${provider}/callback`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ code }),
          }
        );

        console.log('백엔드 응답 상태:', response.status);

        if (!response.ok) {
          const errorData = await response.json();
          console.error('백엔드 에러:', errorData);
          throw new Error(errorData.detail || '토큰 교환 실패');
        }

        const data = await response.json();
        console.log('토큰 교환 성공');

        // 3. JWT 토큰을 localStorage에 저장
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        localStorage.setItem('user', JSON.stringify(data.user));

        setStatus('success');
        setMessage('로그인 성공! 대시보드로 이동합니다...');

        // 4. 대시보드로 리디렉션
        setTimeout(() => {
          navigate('/dashboard');
        }, 1500);
      } catch (error) {
        console.error('OAuth 콜백 처리 오류:', error);
        setStatus('error');
        setMessage(error.message || '로그인에 실패했습니다.');

        // 5초 후 로그인 페이지로 이동
        setTimeout(() => {
          navigate('/login');
        }, 5000);
      }
    };

    handleCallback();
  }, [searchParams, provider, navigate]);

  return (
    <div className="auth-callback">
      <div className="callback-container">
        {status === 'loading' && (
          <>
            <div className="spinner"></div>
            <h2>{message}</h2>
            <p>잠시만 기다려주세요...</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="success-icon">✅</div>
            <h2>{message}</h2>
            <p>환영합니다!</p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="error-icon">❌</div>
            <h2>로그인 실패</h2>
            <p>{message}</p>
            <button onClick={() => navigate('/login')} className="retry-button">
              다시 시도
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default AuthCallback;
