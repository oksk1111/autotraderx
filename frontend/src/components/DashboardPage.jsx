import { useQuery } from "react-query";
import axios from "axios";
import MetricsGrid from "./MetricsGrid";
import TradeTable from "./TradeTable";
import AccountInfo from "./AccountInfo";
import TradingConfigPanel from "./TradingConfigPanel";
import AutonomyBoard from "./AutonomyBoard";

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
  
  const autonomyQuery = useQuery(["autonomy"], async () => {
    const { data } = await api.get("/dashboard/autonomy_status");
    return data;
  }, { refetchInterval: 7000 });

  return (
    <div className="page">
      <header className="hero-header">
        <div>
          <h1>AutoTrader X</h1>
          <p>LLM Autonomous Prepositioning Desk</p>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <span className="badge">LIVE</span>
          <span className="badge secondary">NO MANUAL OVERRIDE</span>
        </div>
      </header>

      <div className="grid-2">
        <AccountInfo />
        <TradingConfigPanel />
      </div>

      <MetricsGrid 
        metrics={metricsQuery.data} 
        snapshot={snapshotQuery.data}
        autonomy={autonomyQuery.data}
        loading={metricsQuery.isLoading || snapshotQuery.isLoading} 
      />

      <AutonomyBoard autonomy={autonomyQuery.data} loading={autonomyQuery.isLoading} />

      <TradeTable trades={tradesQuery.data} loading={tradesQuery.isLoading} />
    </div>
  );
}

export default DashboardPage;
