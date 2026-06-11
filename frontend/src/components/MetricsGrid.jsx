function fmtKrw(v) {
  if (v === null || v === undefined) return "-";
  return new Intl.NumberFormat("ko-KR").format(Math.round(v)) + " KRW";
}

function MetricsGrid({ metrics, snapshot, loading }) {
  if (loading) return <div className="loading mb-4">Loading metrics...</div>;

  const dailyPnl = metrics?.daily_realized_pnl_krw ?? 0;
  const startEq = metrics?.daily_start_equity ?? 0;
  const pnlPct = startEq > 0 ? ((dailyPnl / startEq) * 100).toFixed(2) : "0.00";

  const items = [
    { label: "Live Equity", value: fmtKrw(metrics?.live_equity) },
    { label: "Daily P&L", value: `${fmtKrw(dailyPnl)} (${pnlPct}%)`, isPositive: dailyPnl >= 0 },
    { label: "Daily Trades", value: `${metrics?.daily_trade_count ?? 0}` },
    { label: "Open Positions", value: metrics?.live_open_positions ?? 0 },
    { label: "Mode", value: (metrics?.strategy_mode ?? "auto").toUpperCase() },
  ];

  return (
    <div className="grid-5">
      {items.map((item) => (
        <div key={item.label} className="stat-card">
          <div className="stat-label">{item.label}</div>
          <div className={`stat-value ${item.isPositive === true ? "text-success" : item.isPositive === false ? "text-danger" : ""}`}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}

export default MetricsGrid;
