import { useQuery } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

function AccountInfo() {
  const { data, isLoading } = useQuery(
    ["account"],
    async () => {
      const { data } = await api.get("/account/balance");
      return data;
    },
    { refetchInterval: 10000 } // 10초마다 갱신
  );

  if (isLoading) {
    return (
      <div className="panel">
        <h2>💰 계정 정보</h2>
        <p className="loading">로딩 중...</p>
      </div>
    );
  }

  const formatNumber = (num) => {
    return new Intl.NumberFormat('ko-KR').format(Math.round(num));
  };

  const formatPercent = (num) => {
    const sign = num >= 0 ? '+' : '';
    return `${sign}${num.toFixed(2)}%`;
  };

  return (
    <div className="panel">
      <h2>💰 계정 정보</h2>
      
      <div style={{ marginBottom: '20px', padding: '15px', background: '#1a1a1a', borderRadius: '8px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
          <div>
            <div style={{ color: '#888', fontSize: '0.9rem' }}>가용 KRW</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#4CAF50' }}>
              ₩{formatNumber(data?.krw_balance || 0)}
            </div>
          </div>
          <div>
            <div style={{ color: '#888', fontSize: '0.9rem' }}>총 자산</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
              ₩{formatNumber(data?.total_asset_value || 0)}
            </div>
          </div>
        </div>
      </div>

      {data?.holdings && data.holdings.length > 0 ? (
        <div>
          <h3 style={{ marginBottom: '10px', color: '#888' }}>보유 코인 ({data.total_positions}개)</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {data.holdings.map((holding) => (
              <div 
                key={holding.market} 
                style={{ 
                  padding: '12px', 
                  background: '#1a1a1a', 
                  borderRadius: '6px',
                  borderLeft: `3px solid ${holding.profit_loss >= 0 ? '#4CAF50' : '#f44336'}`
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div>
                    <span style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>{holding.currency}</span>
                    <span style={{ color: '#888', marginLeft: '8px', fontSize: '0.9rem' }}>
                      {holding.amount.toFixed(4)}개
                    </span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ 
                      fontWeight: 'bold',
                      color: holding.profit_loss >= 0 ? '#4CAF50' : '#f44336'
                    }}>
                      {formatPercent(holding.profit_loss_rate)}
                    </div>
                    <div style={{ fontSize: '0.9rem', color: '#888' }}>
                      {holding.profit_loss >= 0 ? '+' : ''}₩{formatNumber(holding.profit_loss)}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#888' }}>
                  <div>평단: ₩{formatNumber(holding.avg_buy_price)}</div>
                  <div>현재: ₩{formatNumber(holding.current_price)}</div>
                  <div>평가: ₩{formatNumber(holding.current_value)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p style={{ color: '#888', textAlign: 'center', padding: '20px' }}>
          보유 중인 코인이 없습니다
        </p>
      )}
    </div>
  );
}

export default AccountInfo;
