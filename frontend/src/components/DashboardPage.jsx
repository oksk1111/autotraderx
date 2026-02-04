import { useQuery } from "react-query";
import axios from "axios";
import MetricsGrid from "./MetricsGrid";
import TradeTable from "./TradeTable";
import AccountInfo from "./AccountInfo";
import TradingConfigPanel from "./TradingConfigPanel";
import PersonaPanel from "./PersonaPanel";

const api = axios.create({ baseURL: "/api" });

function DashboardPage() {
  const metricsQuery = useQuery(["metrics"], async () => {
    const { data } = await api.get("/dashboard/metrics");
    return data;
  });

  const tradesQuery = useQuery(["trades"], async () => {
    const { data } = await api.get("/dashboard/logs");
    return data;
  });

  const snapshotQuery = useQuery(["snapshot"], async () => {
    const { data } = await api.get("/dashboard/snapshot");
    return data;
  });
  
  const personaQuery = useQuery(["personas"], async () => {
    const { data } = await api.get("/dashboard/personas_status");
    return data;
  }, { refetchInterval: 5000 }); // Refresh every 5s

  return (
    <div className="page">
      <header>
        <div>
          <h1>AutoTrader X</h1>
          <p>Autonomous Crypto Trading System</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <span className="badge">LIVE</span>
        </div>
      </header>

      {/* Top Row: Account & Config */}
      <div className="grid-2">
        <AccountInfo />
        <TradingConfigPanel />
      </div>

      {/* Middle Row: Key Metrics */}
      <MetricsGrid 
        metrics={metricsQuery.data} 
        snapshot={snapshotQuery.data}
        loading={metricsQuery.isLoading || snapshotQuery.isLoading} 
      />
      
      {/* Persona Strategy Board */}
      <div style={{ marginTop: '1.5rem' }}>
        <PersonaPanel data={personaQuery.data} loading={personaQuery.isLoading} />
      </div>

      {/* Bottom Row: Recent Trades */}
      <TradeTable trades={tradesQuery.data} loading={tradesQuery.isLoading} />
    </div>
  );
}

export default DashboardPage;
