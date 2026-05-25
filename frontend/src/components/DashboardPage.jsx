import { useQuery } from "react-query";
import axios from "axios";
import MetricsGrid from "./MetricsGrid";
import TradeTable from "./TradeTable";
import AccountInfo from "./AccountInfo";
import TradingConfigPanel from "./TradingConfigPanel";
import StrategyStatus from "./StrategyStatus";
import RiskPanel from "./RiskPanel";
import ShadowComparePanel from "./ShadowComparePanel";

const api = axios.create({ baseURL: "/api" });

function DashboardPage() {
  const metricsQuery = useQuery(["metrics"], async () => {
    const { data } = await api.get("/dashboard/metrics");
    return data;
  }, { refetchInterval: 5000 });

  const tradesQuery = useQuery(["trades"], async () => {
    const { data } = await api.get("/dashboard/logs");
    return data;
  }, { refetchInterval: 10000 });

  const snapshotQuery = useQuery(["snapshot"], async () => {
    const { data } = await api.get("/dashboard/snapshot");
    return data;
  }, { refetchInterval: 5000 });

  const liveOn = metricsQuery.data?.live_trading_enabled;

  return (
    <div className="page">
      <header className="hero-header">
        <div>
          <h1>AutoTrader X</h1>
          <p>Capital-First Regime-Switching Engine · v5.0</p>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <span className={`badge ${liveOn ? "danger" : "secondary"}`}>
            {liveOn ? "LIVE TRADING" : "PAPER ONLY"}
          </span>
          <span className="badge secondary">Risk 1% / Trade</span>
        </div>
      </header>

      <div className="grid-2">
        <AccountInfo />
        <TradingConfigPanel />
      </div>

      <MetricsGrid
        metrics={metricsQuery.data}
        snapshot={snapshotQuery.data}
        loading={metricsQuery.isLoading || snapshotQuery.isLoading}
      />

      <StrategyStatus />
      <RiskPanel />
      <ShadowComparePanel />

      <TradeTable trades={tradesQuery.data} loading={tradesQuery.isLoading} />
    </div>
  );
}

export default DashboardPage;
