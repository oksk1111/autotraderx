import { useQuery, useMutation, useQueryClient } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

function TradingConfigPanel() {
  const queryClient = useQueryClient();

  const { data: config, isLoading } = useQuery(
    ["config"],
    async () => {
      const { data } = await api.get("/config/");
      return data;
    },
    { refetchInterval: 10000 }
  );

  const updateMutation = useMutation(
    async (newConfig) => {
      const { data } = await api.put("/config/", newConfig);
      return data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["config"]);
      },
    }
  );

  const handleToggleActive = () => {
    if (config) {
      updateMutation.mutate({ ...config, is_active: !config.is_active });
    }
  };

  if (isLoading) return <div className="panel loading">Loading config...</div>;

  const currentCycle = config?.trading_cycle_seconds || 180;
  const isActive = config?.is_active || false;

  return (
    <div className="panel">
      <div className="flex-between mb-4">
        <h2>Autonomous Control</h2>
        <div className="flex-between" style={{ gap: "1rem" }}>
          <span className={`badge ${isActive ? "text-success" : "text-danger"}`} 
                style={{ background: isActive ? "rgba(26, 171, 120, 0.13)" : "rgba(205, 69, 69, 0.14)", border: "none" }}>
            {isActive ? 'RUNNING' : 'STOPPED'}
          </span>
          <button 
            onClick={handleToggleActive}
            className="btn-primary"
            style={{ background: isActive ? 'var(--danger)' : 'var(--success)' }}
          >
            {isActive ? 'Stop Trading' : 'Start Trading'}
          </button>
        </div>
      </div>

      <div className="mini-card">
        <label className="stat-label" style={{ display: "block", marginBottom: "0.5rem" }}>Strategy Mode</label>
        <div style={{ fontWeight: 700 }}>
          LLM Autonomous Trading (Full Auto)
        </div>
        <div style={{ marginTop: "0.6rem", color: "var(--text-muted)", fontSize: "0.88rem" }}>
          You do not select strategy. Engine automatically chooses regime and candidates from historical data.
        </div>
      </div>

      <div className="config-list">
        <div><span>Cycle</span><strong>{currentCycle}s</strong></div>
        <div><span>Min Confidence</span><strong>{((config?.min_confidence || 0.75) * 100).toFixed(0)}%</strong></div>
        <div><span>Stop Loss</span><strong>{(config?.stop_loss_percent || 1.5).toFixed(1)}%</strong></div>
        <div><span>Take Profit</span><strong>{(config?.take_profit_percent || 3.0).toFixed(1)}%</strong></div>
      </div>
    </div>
  );
}

export default TradingConfigPanel;
