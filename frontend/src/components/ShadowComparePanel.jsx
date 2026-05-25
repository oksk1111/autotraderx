import { useQuery } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

function fmtKrw(v) {
  if (v === null || v === undefined) return "-";
  return new Intl.NumberFormat("ko-KR").format(Math.round(v));
}

function ShadowComparePanel() {
  const q = useQuery(["shadow-compare"], async () => {
    const { data } = await api.get("/shadow/compare?days=7");
    return data;
  }, { refetchInterval: 30000 });

  const series = (q.data?.series || []).slice(-30);
  if (!series.length) {
    return (
      <div className="panel">
        <div className="panel-header"><h2>Paper vs Live (7d)</h2></div>
        <div className="panel-body">
          <p className="text-muted">Shadow data will appear once the engine has run a few cycles.</p>
        </div>
      </div>
    );
  }

  const latest = series[series.length - 1];
  const first = series[0];
  const paperDelta = latest.paper_equity - first.paper_equity;
  const liveDelta = (latest.live_equity ?? 0) - (first.live_equity ?? 0);

  return (
    <div className="panel">
      <div className="panel-header"><h2>Paper vs Live (Shadow Compare)</h2></div>
      <div className="panel-body">
        <div className="grid-3">
          <div className="stat-card">
            <div className="stat-label">Paper Equity (now)</div>
            <div className="stat-value">{fmtKrw(latest.paper_equity)}</div>
            <div className={`stat-sub ${paperDelta >= 0 ? "text-success" : "text-danger"}`}>
              {paperDelta >= 0 ? "+" : ""}{fmtKrw(paperDelta)}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Live Equity (now)</div>
            <div className="stat-value">{fmtKrw(latest.live_equity)}</div>
            <div className={`stat-sub ${liveDelta >= 0 ? "text-success" : "text-danger"}`}>
              {liveDelta >= 0 ? "+" : ""}{fmtKrw(liveDelta)}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Daily P&L</div>
            <div className={`stat-value ${(latest.daily_pnl_pct ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
              {((latest.daily_pnl_pct ?? 0) * 100).toFixed(2)}%
            </div>
          </div>
        </div>

        <div className="table-wrapper" style={{ marginTop: "1rem" }}>
          <table className="table">
            <thead>
              <tr><th>Time</th><th>Paper</th><th>Live</th><th>Open (P/L)</th></tr>
            </thead>
            <tbody>
              {series.slice().reverse().map((row, idx) => (
                <tr key={`${row.ts}-${idx}`}>
                  <td>{row.ts ? new Date(row.ts).toLocaleString() : "-"}</td>
                  <td>{fmtKrw(row.paper_equity)}</td>
                  <td>{fmtKrw(row.live_equity)}</td>
                  <td>{row.paper_open} / {row.live_open}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default ShadowComparePanel;
