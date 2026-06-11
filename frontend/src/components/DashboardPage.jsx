import { useEffect } from "react";
import { useQuery, useQueryClient } from "react-query";
import axios from "axios";
import MetricsGrid from "./MetricsGrid";
import TradeTable from "./TradeTable";
import AccountInfo from "./AccountInfo";
import TradingConfigPanel from "./TradingConfigPanel";
import StrategyStatus from "./StrategyStatus";
import RiskPanel from "./RiskPanel";

const api = axios.create({ baseURL: "/api" });

function DashboardPage() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/api/dashboard/ws`;
    
    let ws;
    let reconnectTimeout;

    function connect() {
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.metrics) queryClient.setQueryData(["metrics"], data.metrics);
          if (data.snapshot) queryClient.setQueryData(["snapshot"], data.snapshot);
          if (data.trades) queryClient.setQueryData(["trades"], data.trades);
          if (data.config) queryClient.setQueryData(["config"], data.config);
          if (data["risk-state"]) queryClient.setQueryData(["risk-state"], data["risk-state"]);
          if (data["risk-events"]) queryClient.setQueryData(["risk-events"], data["risk-events"]);
          if (data.account) queryClient.setQueryData(["account"], data.account);
          if (data["strategy-status"]) queryClient.setQueryData(["strategy-status"], data["strategy-status"]);
        } catch (err) {
          console.error("WS parse error:", err);
        }
      };

      ws.onclose = () => {
        reconnectTimeout = setTimeout(() => {
          connect();
        }, 3000);
      };

      ws.onerror = (err) => {
        console.error("WS error:", err);
        ws.close();
      };
    }

    connect();

    return () => {
      if (ws) ws.close();
      clearTimeout(reconnectTimeout);
    };
  }, [queryClient]);

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

  return (
    <div className="page">
      <header className="hero-header">
        <div>
          <h1>AutoTrader X</h1>
          <p>Capital-First Live Trading Engine · v8.0</p>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <span className="badge danger">LIVE TRADING</span>
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

      <TradeTable trades={tradesQuery.data} loading={tradesQuery.isLoading} />
    </div>
  );
}

export default DashboardPage;
