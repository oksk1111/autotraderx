import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

const CYCLE_PRESETS = [
  { label: "1m", value: 60 },
  { label: "3m", value: 180 },
  { label: "5m", value: 300 },
  { label: "10m", value: 600 },
  { label: "30m", value: 1800 },
  { label: "1h", value: 3600 },
];

function TradingConfigPanel() {
  const queryClient = useQueryClient();
  const [customCycle, setCustomCycle] = useState("");

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

  const handlePresetClick = (seconds) => {
    if (config) {
      updateMutation.mutate({ ...config, trading_cycle_seconds: seconds });
    }
  };

  const handleToggleActive = () => {
    if (config) {
      updateMutation.mutate({ ...config, is_active: !config.is_active });
    }
  };

  if (isLoading) return <div className="panel loading">Loading config...</div>;

  const currentCycle = config?.trading_cycle_seconds || 60;
  const isActive = config?.is_active || false;

  return (
    <div className="panel">
      <div className="flex-between mb-4">
        <h2>System Control</h2>
        <div className="flex-between" style={{ gap: '1rem' }}>
          <span className={`badge ${isActive ? 'text-success' : 'text-danger'}`} 
                style={{ background: isActive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', border: 'none' }}>
            {isActive ? 'RUNNING' : 'STOPPED'}
          </span>
          <button 
            onClick={handleToggleActive}
            className={isActive ? 'btn-primary' : 'btn-primary'}
            style={{ background: isActive ? 'var(--danger)' : 'var(--success)' }}
          >
            {isActive ? 'Stop Trading' : 'Start Trading'}
          </button>
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label className="stat-label" style={{ display: 'block', marginBottom: '0.5rem' }}>Trading Cycle</label>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {CYCLE_PRESETS.map((preset) => (
            <button
              key={preset.value}
              onClick={() => handlePresetClick(preset.value)}
              style={{
                padding: '0.5rem 1rem',
                borderRadius: '6px',
                border: '1px solid var(--border)',
                background: currentCycle === preset.value ? 'var(--primary)' : 'var(--bg-card)',
                color: currentCycle === preset.value ? 'white' : 'var(--text-muted)',
                cursor: 'pointer'
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default TradingConfigPanel;
