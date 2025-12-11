function TradeTable({ trades = [], loading }) {
  return (
    <section className="panel">
      <div className="flex-between mb-4">
        <h2>Recent Activity</h2>
        <button className="btn-primary" style={{ fontSize: '0.8rem', padding: '0.25rem 0.75rem', background: 'transparent', border: '1px solid var(--border)' }}>
          View All
        </button>
      </div>
      
      {loading ? (
        <p className="loading">Loading trades...</p>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Market</th>
                <th>Side</th>
                <th>Price</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {trades?.length > 0 ? trades.map((trade, idx) => (
                <tr key={trade.id || idx}>
                  <td className="text-muted">{new Date(trade.created_at).toLocaleTimeString()}</td>
                  <td style={{ fontWeight: 600 }}>{trade.market}</td>
                  <td>
                    <span className={`badge ${trade.side === 'BUY' ? 'text-success' : 'text-danger'}`} 
                          style={{ background: trade.side === 'BUY' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', border: 'none' }}>
                      {trade.side}
                    </span>
                  </td>
                  <td>₩{new Intl.NumberFormat('ko-KR').format(trade.price || 0)}</td>
                  <td className="text-muted" style={{ fontSize: '0.85rem' }}>{trade.reason}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No recent trades recorded
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default TradeTable;
