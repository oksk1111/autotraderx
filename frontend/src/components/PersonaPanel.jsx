import React from 'react';

function PersonaPanel({ data, loading }) {
  if (loading) return <div className="panel">Loading Personas...</div>;
  
  const hasData = data && Object.keys(data).length > 0;
  const markets = hasData ? Object.keys(data).sort() : [];

  return (
    <section className="panel">
      <h2>Persona Strategy Board</h2>
      <p style={{fontSize: '0.9rem', color: '#888', marginBottom: '1rem'}}>
        Real-time analysis by AI personas investing with distinct philosophies.
      </p>
      
      {!hasData ? (
        <div style={{padding: '2rem', textAlign: 'center', color: '#666'}}>
          Waiting for market cycle analysis...
        </div>
      ) : (
        <div className="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Market</th>
                        <th>Warren Buffett (Value)</th>
                        <th>Larry Williams (Vol)</th>
                        <th>Trend Follower (Mom)</th>
                    </tr>
                </thead>
                <tbody>
                    {markets.map(m => {
                        const personas = data[m] || [];
                        const buffett = personas.find(p => p.persona.includes("Warren")) || {};
                        const larry = personas.find(p => p.persona.includes("Larry")) || {};
                        const momentum = personas.find(p => p.persona.includes("Trend")) || {};

                        const getCell = (p) => {
                             if (!p.action) return <span style={{color: '#666'}}>-</span>;
                             
                             let color = '#888';
                             if (p.action === 'BUY') color = '#4caf50';
                             if (p.action === 'SELL') color = '#f44336';
                             
                             return (
                                 <div>
                                    <span style={{color: color, fontWeight: 'bold'}}>
                                        {p.action}
                                    </span>
                                    {p.confidence > 0 && (
                                        <span style={{fontSize: '0.8em', marginLeft: '6px', color: '#aaa'}}>
                                            {(p.confidence*100).toFixed(0)}%
                                        </span>
                                    )}
                                    <div style={{fontSize: '0.7em', color: '#666', marginTop: '2px', maxWidth: '200px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
                                        {p.reason}
                                    </div>
                                 </div>
                             )
                        };

                        return (
                            <tr key={m}>
                                <td style={{ fontWeight: 600 }}>{m.replace('KRW-', '')}</td>
                                <td>{getCell(buffett)}</td>
                                <td>{getCell(larry)}</td>
                                <td>{getCell(momentum)}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
      )}
    </section>
  );
}

export default PersonaPanel;
