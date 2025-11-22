function MetricsGrid({ metrics, loading }) {
  const items = [
    { label: "Trades", value: metrics?.trade_count ?? "-" },
    { label: "Last Trade (₩)", value: metrics?.last_trade_amount ?? "-" },
    { label: "Confidence", value: metrics?.last_confidence ?? "-" }
  ];
  return (
    <section className="panel">
      <h2>Execution Metrics</h2>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <div className="metrics">
          {items.map((item) => (
            <div key={item.label}>
              <p className="metric-label">{item.label}</p>
              <p className="metric-value">{item.value}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default MetricsGrid;
