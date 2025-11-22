function TradeTable({ trades = [], loading }) {
  return (
    <section className="panel">
      <h2>Recent Trades</h2>
      {loading ? (
        <p>Loading...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Market</th>
              <th>Side</th>
              <th>Amount</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {trades?.map((trade) => (
              <tr key={trade.id}>
                <td>{new Date(trade.created_at).toLocaleTimeString()}</td>
                <td>{trade.market}</td>
                <td>{trade.side}</td>
                <td>{trade.amount}</td>
                <td>{trade.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default TradeTable;
