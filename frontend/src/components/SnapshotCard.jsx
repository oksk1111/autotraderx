function SnapshotCard({ data, loading }) {
  return (
    <div className="panel">
      <h2>System Snapshot</h2>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <dl className="snapshot">
          <div>
            <dt>Timestamp</dt>
            <dd>{new Date(data?.timestamp ?? Date.now()).toLocaleString()}</dd>
          </div>
          <div>
            <dt>Active Markets</dt>
            <dd>{data?.active_markets?.join(", ")}</dd>
          </div>
          <div>
            <dt>Open Positions</dt>
            <dd>{data?.open_positions}</dd>
          </div>
          <div>
            <dt>24h P&L</dt>
            <dd>{data?.pnl_24h}%</dd>
          </div>
          <div>
            <dt>Emergency Triggers</dt>
            <dd>{data?.emergency_triggers_today}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

export default SnapshotCard;
