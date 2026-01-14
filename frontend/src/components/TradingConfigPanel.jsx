import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

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

  const handleStrategyChange = (e) => {
    if (config) {
      updateMutation.mutate({ ...config, strategy_option: e.target.value });
    }
  };

  if (isLoading) return <div className="panel loading">Loading config...</div>;

  const currentCycle = config?.trading_cycle_seconds || 60;
  const currentStrategy = config?.strategy_option || "reversal_strategy";
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

      <div style={{ marginBottom: '1.5rem', padding: '10px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
        <label className="stat-label" style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Strategy Options</label>
        <select 
            value={currentStrategy} 
            onChange={handleStrategyChange}
            style={{ 
                width: '100%', 
                padding: '0.8rem', 
                background: 'var(--bg-secondary)', 
                color: 'var(--text-primary)', 
                border: '1px solid var(--border-color)',
                borderRadius: '4px',
                fontSize: '1rem',
                cursor: 'pointer'
            }}
        >
            <option value="momentum_strategy" style={{ background: '#1e293b', color: '#f1f5f9' }}>Option 1: 추격 매수 (Momentum / Pump)</option>
            <option value="reversal_strategy" style={{ background: '#1e293b', color: '#f1f5f9' }}>Option 2: 역추세 매매 (Reversal: Peak Sell / Dip Buy)</option>
        </select>
        <div style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {currentStrategy === 'momentum_strategy' 
                ? "🚀 급등 시 매수하여 상승세에 편승합니다." 
                : "📉 급락 시 매수, 급등 시 매도하여 변동성을 활용합니다."}
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <label className="stat-label" style={{ display: 'block', marginBottom: '0.5rem' }}>Trading Cycle</label>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Managed automatically by Pump Detection System (Real-time)
        </div>
      </div>
    </div>
  );
}

export default TradingConfigPanel;
