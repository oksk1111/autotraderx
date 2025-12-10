/**
 * Upbit API 키 등록 폼
 */
import React, { useState } from 'react';

const ApiKeyRegistration = () => {
  const [formData, setFormData] = useState({
    access_key: '',
    secret_key: '',
    key_name: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      // JWT 토큰 가져오기
      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('로그인이 필요합니다.');
      }

      // API 키 등록 요청
      const response = await fetch('http://localhost:8000/api/auth/api-keys', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API 키 등록에 실패했습니다.');
      }

      const data = await response.json();
      
      setMessage({
        type: 'success',
        text: 'API 키가 성공적으로 등록되었습니다! 이제 자동 매매를 시작할 수 있습니다.'
      });

      // 폼 초기화
      setFormData({ access_key: '', secret_key: '', key_name: '' });

    } catch (error) {
      setMessage({
        type: 'error',
        text: error.message
      });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  return (
    <div className="api-key-form">
      <h2>Upbit API 키 등록</h2>
      <p className="description">
        자동 매매를 시작하려면 Upbit API 키를 등록해주세요.<br />
        <strong>주의:</strong> 출금 권한은 절대 허용하지 마세요. (조회 + 거래 권한만)
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>키 별칭 (선택)</label>
          <input
            type="text"
            name="key_name"
            placeholder="예: 메인 계좌, 테스트 계좌"
            value={formData.key_name}
            onChange={handleChange}
          />
        </div>

        <div className="form-group">
          <label>Access Key *</label>
          <input
            type="text"
            name="access_key"
            placeholder="Upbit Access Key"
            value={formData.access_key}
            onChange={handleChange}
            required
            minLength={10}
          />
        </div>

        <div className="form-group">
          <label>Secret Key *</label>
          <input
            type="password"
            name="secret_key"
            placeholder="Upbit Secret Key"
            value={formData.secret_key}
            onChange={handleChange}
            required
            minLength={10}
          />
        </div>

        {message.text && (
          <div className={`message ${message.type}`}>
            {message.text}
          </div>
        )}

        <button type="submit" disabled={loading}>
          {loading ? '등록 중...' : 'API 키 등록'}
        </button>
      </form>

      <div className="help-text">
        <h3>📘 Upbit API 키 발급 방법</h3>
        <ol>
          <li><a href="https://upbit.com/mypage/open_api_management" target="_blank" rel="noopener noreferrer">
            Upbit Open API 관리</a> 페이지 접속</li>
          <li>"Open API Key 발급" 버튼 클릭</li>
          <li>권한 설정:
            <ul>
              <li>✅ 자산 조회</li>
              <li>✅ 주문 조회</li>
              <li>✅ 주문하기</li>
              <li>❌ <strong>출금 (절대 허용하지 마세요!)</strong></li>
            </ul>
          </li>
          <li>생성된 Access Key와 Secret Key를 위 폼에 입력</li>
        </ol>
      </div>

      <style jsx>{`
        .api-key-form {
          max-width: 600px;
          margin: 30px auto;
          padding: 30px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        h2 {
          margin-bottom: 10px;
          color: #333;
        }

        .description {
          color: #666;
          margin-bottom: 30px;
          line-height: 1.6;
        }

        .description strong {
          color: #e74c3c;
        }

        .form-group {
          margin-bottom: 20px;
        }

        label {
          display: block;
          margin-bottom: 8px;
          font-weight: 500;
          color: #333;
        }

        input {
          width: 100%;
          padding: 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
        }

        input:focus {
          outline: none;
          border-color: #3498db;
        }

        button {
          width: 100%;
          padding: 14px;
          background: #3498db;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          transition: background 0.2s;
        }

        button:hover:not(:disabled) {
          background: #2980b9;
        }

        button:disabled {
          background: #bdc3c7;
          cursor: not-allowed;
        }

        .message {
          padding: 12px;
          margin: 20px 0;
          border-radius: 6px;
          font-size: 14px;
        }

        .message.success {
          background: #d4edda;
          color: #155724;
          border: 1px solid #c3e6cb;
        }

        .message.error {
          background: #f8d7da;
          color: #721c24;
          border: 1px solid #f5c6cb;
        }

        .help-text {
          margin-top: 40px;
          padding-top: 30px;
          border-top: 1px solid #eee;
        }

        .help-text h3 {
          margin-bottom: 15px;
          color: #333;
        }

        .help-text ol {
          padding-left: 20px;
        }

        .help-text li {
          margin-bottom: 10px;
          line-height: 1.6;
        }

        .help-text ul {
          margin-top: 8px;
          padding-left: 20px;
        }

        .help-text a {
          color: #3498db;
          text-decoration: none;
        }

        .help-text a:hover {
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
};

export default ApiKeyRegistration;
