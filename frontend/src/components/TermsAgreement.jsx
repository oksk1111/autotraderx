/**
 * 약관 동의 컴포넌트
 */
import React, { useState } from 'react';

const TermsAgreement = ({ onComplete }) => {
  const [agreements, setAgreements] = useState({
    terms_agreed: false,
    privacy_agreed: false,
    marketing_agreed: false
  });
  const [loading, setLoading] = useState(false);

  const handleCheckbox = (name) => {
    setAgreements({
      ...agreements,
      [name]: !agreements[name]
    });
  };

  const handleAllAgree = () => {
    const allAgreed = agreements.terms_agreed && agreements.privacy_agreed;
    setAgreements({
      terms_agreed: !allAgreed,
      privacy_agreed: !allAgreed,
      marketing_agreed: !allAgreed
    });
  };

  const handleSubmit = async () => {
    // 필수 약관 체크
    if (!agreements.terms_agreed || !agreements.privacy_agreed) {
      alert('필수 약관에 동의해주세요.');
      return;
    }

    setLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      
      const response = await fetch('http://localhost:8000/api/auth/terms/agree', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(agreements)
      });

      if (!response.ok) {
        throw new Error('약관 동의 처리에 실패했습니다.');
      }

      // 완료 콜백 호출
      if (onComplete) {
        onComplete();
      }

    } catch (error) {
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };

  const allRequired = agreements.terms_agreed && agreements.privacy_agreed;

  return (
    <div className="terms-agreement">
      <h2>서비스 이용 약관</h2>
      <p className="subtitle">AutoTrader 서비스를 이용하기 위해 약관에 동의해주세요.</p>

      <div className="all-agree">
        <label>
          <input
            type="checkbox"
            checked={agreements.terms_agreed && agreements.privacy_agreed && agreements.marketing_agreed}
            onChange={handleAllAgree}
          />
          <span className="label-text">전체 동의</span>
        </label>
      </div>

      <div className="agreements">
        <div className="agreement-item">
          <label>
            <input
              type="checkbox"
              checked={agreements.terms_agreed}
              onChange={() => handleCheckbox('terms_agreed')}
            />
            <span className="label-text">
              <strong>[필수]</strong> 이용약관 동의
            </span>
          </label>
          <a href="/terms" target="_blank" className="view-link">보기</a>
        </div>

        <div className="agreement-item">
          <label>
            <input
              type="checkbox"
              checked={agreements.privacy_agreed}
              onChange={() => handleCheckbox('privacy_agreed')}
            />
            <span className="label-text">
              <strong>[필수]</strong> 개인정보 처리방침 동의
            </span>
          </label>
          <a href="/privacy" target="_blank" className="view-link">보기</a>
        </div>

        <div className="agreement-item">
          <label>
            <input
              type="checkbox"
              checked={agreements.marketing_agreed}
              onChange={() => handleCheckbox('marketing_agreed')}
            />
            <span className="label-text">
              [선택] 마케팅 정보 수신 동의
            </span>
          </label>
        </div>
      </div>

      <button
        onClick={handleSubmit}
        disabled={!allRequired || loading}
        className="submit-button"
      >
        {loading ? '처리 중...' : '동의하고 계속'}
      </button>

      <style jsx>{`
        .terms-agreement {
          max-width: 500px;
          margin: 50px auto;
          padding: 40px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }

        h2 {
          text-align: center;
          margin-bottom: 10px;
          color: #333;
        }

        .subtitle {
          text-align: center;
          color: #666;
          margin-bottom: 30px;
        }

        .all-agree {
          padding: 16px;
          background: #f8f9fa;
          border-radius: 8px;
          margin-bottom: 20px;
        }

        .all-agree label {
          display: flex;
          align-items: center;
          cursor: pointer;
        }

        .all-agree .label-text {
          font-weight: 600;
          font-size: 16px;
        }

        .agreements {
          border: 1px solid #e9ecef;
          border-radius: 8px;
          padding: 20px;
          margin-bottom: 20px;
        }

        .agreement-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 0;
          border-bottom: 1px solid #e9ecef;
        }

        .agreement-item:last-child {
          border-bottom: none;
        }

        .agreement-item label {
          display: flex;
          align-items: center;
          cursor: pointer;
          flex: 1;
        }

        input[type="checkbox"] {
          width: 20px;
          height: 20px;
          margin-right: 12px;
          cursor: pointer;
        }

        .label-text {
          font-size: 14px;
          color: #333;
        }

        .label-text strong {
          color: #e74c3c;
        }

        .view-link {
          color: #3498db;
          text-decoration: none;
          font-size: 14px;
          padding: 4px 12px;
          border: 1px solid #3498db;
          border-radius: 4px;
          transition: all 0.2s;
        }

        .view-link:hover {
          background: #3498db;
          color: white;
        }

        .submit-button {
          width: 100%;
          padding: 16px;
          background: #3498db;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.2s;
        }

        .submit-button:hover:not(:disabled) {
          background: #2980b9;
        }

        .submit-button:disabled {
          background: #bdc3c7;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
};

export default TermsAgreement;
