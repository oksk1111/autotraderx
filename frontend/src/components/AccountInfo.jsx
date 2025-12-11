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
      <div className="flex-between mb-4">
        <h2>Account Balance</h2>
        <span className="text-muted" style={{ fontSize: '0.85rem' }}>Updated just now</span>
      </div>
      
      <div className="grid-2" style={{ gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <div className="stat-label">Available KRW</div>
          <div className="stat-value text-success">
            ₩{formatNumber(data?.krw_balance || 0)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Assets</div>
          <div className="stat-value">
            ₩{formatNumber(data?.total_asset_value || 0)}
          </div>
        </div>
      </div>

      {data?.holdings && data.holdings.length > 0 ? (
        <div>
          <h3 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1rem', textTransform: 'uppercase' }}>
            Holdings ({data.total_positions})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {data.holdings.map((holding) => (
              <div 
                key={holding.market} 
                className="stat-card"
                style={{ 
                  padding: '1rem',
                  borderLeft: `3px solid ${holding.profit_loss >= 0 ? 'var(--success)' : 'var(--danger)'}`
                }}
              >
                <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                  <div>
                    <span style={{ fontWeight: '700', fontSize: '1rem' }}>{holding.currency}</span>
                    <span className="text-muted" style={{ marginLeft: '0.5rem', fontSize: '0.85rem' }}>
                      {holding.amount.toFixed(4)}
                    </span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ 
                      fontWeight: '700',
                      color: holding.profit_loss >= 0 ? 'var(--success)' : 'var(--danger)'
                    }}>
                      {formatPercent(holding.profit_loss_rate)}
                    </div>
                  </div>
                </div>
                <div className="flex-between text-muted" style={{ fontSize: '0.8rem' }}>
                  <div>Avg: ₩{formatNumber(holding.avg_buy_price)}</div>
                  <div>Cur: ₩{formatNumber(holding.current_price)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-muted" style={{ textAlign: 'center', padding: '1rem' }}>
          No active positions
        </p>
      )}
    </div>
  );
}

export default AccountInfo;
