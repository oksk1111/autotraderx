import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

function RiskPanel() {
  const qc = useQueryClient();
  const [closePositions, setClosePositions] = useState(true);

  const stateQ = useQuery(["risk-state"], async () => {
    const { data } = await api.get("/risk/state");
    return data;
  });

  const eventsQ = useQuery(["risk-events"], async () => {
    const { data } = await api.get("/risk/events?limit=20");
    return data;
  });

  const toggleMutation = useMutation(
    (enable) => api.post("/risk/kill-switch", { enable, close_positions: closePositions }),
    { onSuccess: () => qc.invalidateQueries(["risk-state"]) }
  );

  const killActive = !!stateQ.data?.kill_switch;
  const events = eventsQ.data || [];

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Risk Guard</h2>
        <span className={`badge ${killActive ? "danger" : "secondary"}`}>
          {killActive ? "KILL SWITCH ACTIVE" : "ARMED"}
        </span>
      </div>
      <div className="panel-body">
        <div className="grid-3">
          <div className="stat-card">
            <div className="stat-label">Daily Loss Limit</div>
            <div className="stat-value">{((stateQ.data?.daily_loss_limit ?? 0) * 100).toFixed(1)}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Risk / Trade</div>
            <div className="stat-value">{((stateQ.data?.risk_per_trade ?? 0) * 100).toFixed(2)}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Max Daily Trades</div>
            <div className="stat-value">{stateQ.data?.max_daily_trades ?? "-"}</div>
          </div>
        </div>

        <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <input
              type="checkbox"
              checked={closePositions}
              onChange={(e) => setClosePositions(e.target.checked)}
            />
            <span>Close all open positions on activation</span>
          </label>
          <button
            className={killActive ? "btn btn-secondary" : "btn btn-danger"}
            onClick={() => toggleMutation.mutate(!killActive)}
            disabled={toggleMutation.isLoading}
          >
            {killActive ? "Disarm Kill Switch" : "Activate Kill Switch"}
          </button>
        </div>

        <h3 style={{ marginTop: "1.5rem" }}>Recent Risk Events</h3>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr><th>Time</th><th>Market</th><th>Guard</th><th>Severity</th><th>Message</th></tr>
            </thead>
            <tbody>
              {events.length === 0 && (
                <tr><td colSpan="5" className="text-muted">No risk events.</td></tr>
              )}
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{e.created_at ? new Date(e.created_at).toLocaleTimeString() : "-"}</td>
                  <td>{e.market || "-"}</td>
                  <td>{e.guard}</td>
                  <td>{e.severity}</td>
                  <td>{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default RiskPanel;
