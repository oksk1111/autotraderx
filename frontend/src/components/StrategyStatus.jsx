import { useQuery } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

function regimeColor(r) {
  switch (r) {
    case "TREND": return "text-success";
    case "RANGE": return "text-muted";
    case "CHAOS": return "text-danger";
    default: return "";
  }
}

function StrategyStatus() {
  const q = useQuery(["strategy-status"], async () => {
    const { data } = await api.get("/strategy/status");
    return data;
  });

  if (q.isLoading) return <div className="loading">Loading regime…</div>;
  const d = q.data;
  if (!d) return null;
  const markets = d.markets || [];

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Regime & Strategy</h2>
        <span className="badge secondary">{(d.mode || "auto").toUpperCase()}</span>
      </div>
      <div className="panel-body">
        <div className="grid-3">
          {markets.map((row) => {
            const reg = row.regime || {};
            return (
              <div key={row.market} className="stat-card">
                <div className="stat-label">{row.market}</div>
                <div className={`stat-value ${regimeColor(reg.regime)}`}>{reg.regime || "-"}</div>
                <div className="stat-sub">
                  ADX {reg.adx != null ? Number(reg.adx).toFixed(1) : "-"} · ATR% {reg.atr_pct != null ? (Number(reg.atr_pct) * 100).toFixed(2) : "-"}
                </div>
                <div className="stat-sub text-muted">stale {row.stale_sec ?? "-"}s · candles {row.candles_1m}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default StrategyStatus;
