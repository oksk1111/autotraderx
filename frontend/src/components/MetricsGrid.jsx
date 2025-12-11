function MetricsGrid({ metrics, snapshot, loading }) {
  if (loading) return <div className="loading mb-4">Loading metrics...</div>;

  const items = [
    { 
      label: "24h P&L", 
      value: snapshot?.pnl_24h ? `${snapshot.pnl_24h}%` : "0.00%",
      isPositive: (snapshot?.pnl_24h || 0) >= 0
    },
    { 
      label: "Active Markets", 
      value: snapshot?.active_markets?.length ?? 0 
    },
    { 
      label: "Total Trades", 
      value: metrics?.trade_count ?? 0 
    },
    { 
      label: "Last Confidence", 
      value: metrics?.last_confidence ? `${(metrics.last_confidence * 100).toFixed(1)}%` : "-" 
    }
  ];

  return (
    <div className="grid-4">
      {items.map((item) => (
        <div key={item.label} className="stat-card">
          <div className="stat-label">{item.label}</div>
          <div className={`stat-value ${item.isPositive === true ? 'text-success' : item.isPositive === false ? 'text-danger' : ''}`}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export default MetricsGrid;
