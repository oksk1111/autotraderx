function AutonomyBoard({ autonomy, loading }) {
  if (loading) {
    return <section className="panel"><h2>Autonomy Engine</h2><p className="loading">Analyzing markets...</p></section>;
  }

  const selected = autonomy?.selected_markets || [];
  const candidates = autonomy?.candidates || [];
  const regimeCounts = autonomy?.regime_counts || {};

  return (
    <section className="panel autonomy-panel">
      <div className="flex-between mb-4">
        <div>
          <h2>Autonomy Engine</h2>
          <p className="panel-subtitle">No manual mode. LLM + ML selects entries automatically.</p>
        </div>
        <span className="mode-pill">PREPOSITIONING</span>
      </div>

      <div className="autonomy-top">
        <div className="mini-card">
          <div className="mini-label">Selected Picks</div>
          <div className="mini-value">{selected.length}</div>
          <div className="mini-list">
            {selected.length > 0 ? selected.map((m) => m.replace("KRW-", "")).join(", ") : "Waiting for cycle"}
          </div>
        </div>
        <div className="mini-card">
          <div className="mini-label">Regime Counts</div>
          <div className="mini-list">
            TREND_UP {regimeCounts.TREND_UP || 0} | RANGE {regimeCounts.RANGE || 0} | RISK_OFF {regimeCounts.RISK_OFF || 0}
          </div>
        </div>
      </div>

      <div className="table-container" style={{ marginTop: "1rem" }}>
        <table>
          <thead>
            <tr>
              <th>Market</th>
              <th>Score</th>
              <th>Regime</th>
              <th>Buy Prob</th>
              <th>Sell Prob</th>
              <th>LLM Ratio</th>
              <th>Risk/Reward</th>
            </tr>
          </thead>
          <tbody>
            {candidates.length > 0 ? (
              candidates.slice(0, 8).map((c, idx) => {
                const reward = (c.take_profit_target || 0) * 100;
                const risk = (c.max_loss_acceptable || 0) * 100;
                return (
                  <tr key={`${c.market}-${idx}`}>
                    <td style={{ fontWeight: 700 }}>{c.market.replace("KRW-", "")}</td>
                    <td>{Number(c.score || 0).toFixed(3)}</td>
                    <td>{c.regime}</td>
                    <td className="text-success">{(Number(c.buy_probability || 0) * 100).toFixed(1)}%</td>
                    <td className="text-danger">{(Number(c.sell_probability || 0) * 100).toFixed(1)}%</td>
                    <td>{(Number(c.investment_ratio || 0) * 100).toFixed(1)}%</td>
                    <td>{reward.toFixed(1)} / {risk.toFixed(1)}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan="7" style={{ textAlign: "center", padding: "1.2rem" }}>No candidate data yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default AutonomyBoard;