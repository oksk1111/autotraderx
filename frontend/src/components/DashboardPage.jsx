import { useQuery } from "react-query";
import axios from "axios";
import MetricsGrid from "./MetricsGrid";
import DecisionTimeline from "./DecisionTimeline";
import TradeTable from "./TradeTable";
import SnapshotCard from "./SnapshotCard";
import AccountInfo from "./AccountInfo";
import TradingConfigPanel from "./TradingConfigPanel";

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

  const decisionsQuery = useQuery(["decisions"], async () => {
    const { data } = await api.get("/dashboard/decisions");
    return data;
  });

  const snapshotQuery = useQuery(["snapshot"], async () => {
    const { data } = await api.get("/dashboard/snapshot");
    return data;
  });

  return (
    <div className="page">
      <header>
        <div>
          <h1>AutoTrader-LXA v3</h1>
          <p>Hybrid ML + dual LLM autonomous crypto trader</p>
        </div>
        <span className="badge">LIVE</span>
      </header>
      <TradingConfigPanel />
      <MetricsGrid metrics={metricsQuery.data} loading={metricsQuery.isLoading} />
      <section className="panel-grid">
        <AccountInfo />
        <SnapshotCard data={snapshotQuery.data} loading={snapshotQuery.isLoading} />
      </section>
      <DecisionTimeline data={decisionsQuery.data} loading={decisionsQuery.isLoading} />
      <TradeTable trades={tradesQuery.data} loading={tradesQuery.isLoading} />
    </div>
  );
}

export default DashboardPage;
