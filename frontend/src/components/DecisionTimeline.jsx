function DecisionTimeline({ data = [], loading }) {
  const getActionColor = (action) => {
    if (action === 'BUY') return '#4CAF50';
    if (action === 'SELL') return '#f44336';
    return '#888';
  };

  const formatRationale = (rationale) => {
    return rationale.split('\n').map((line, idx) => (
      <div key={idx} style={{ marginBottom: '4px' }}>{line}</div>
    ));
  };

  return (
    <div className="panel">
      <h2>🤖 AI 의사결정 타임라인</h2>
      {loading ? (
        <p className="loading">로딩 중...</p>
      ) : data?.length === 0 ? (
        <p style={{ color: '#888', textAlign: 'center', padding: '20px' }}>
          아직 의사결정 기록이 없습니다
        </p>
      ) : (
        <ul className="timeline">
          {data?.slice(0, 10).map((item) => (
            <li key={item.id}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <p className="timeline-title" style={{ margin: 0 }}>
                    <span style={{ fontWeight: 'bold' }}>{item.market}</span>
                    <span 
                      style={{ 
                        marginLeft: '12px',
                        padding: '4px 12px',
                        borderRadius: '12px',
                        background: getActionColor(item.predicted_move) + '20',
                        color: getActionColor(item.predicted_move),
                        fontSize: '0.9rem',
                        fontWeight: 'bold'
                      }}
                    >
                      {item.predicted_move}
                    </span>
                  </p>
                  <span style={{ fontSize: '0.85rem', color: '#888' }}>
                    {new Date(item.created_at).toLocaleString('ko-KR', { 
                      month: 'short', 
                      day: 'numeric', 
                      hour: '2-digit', 
                      minute: '2-digit' 
                    })}
                  </span>
                </div>
                
                <p className="timeline-meta" style={{ marginBottom: '8px' }}>
                  <span style={{ fontWeight: 'bold', color: '#fff' }}>
                    신뢰도 {Math.round(item.confidence * 100)}%
                  </span>
                  {' · '}
                  Groq {item.groq_alignment ? "✅" : "❌"}
                  {' · '}
                  Ollama {item.ollama_alignment ? "✅" : "❌"}
                  {item.emergency_triggered && (
                    <span style={{ 
                      marginLeft: '8px', 
                      color: '#ff6b6b', 
                      fontWeight: 'bold' 
                    }}>
                      ⚠️ 긴급
                    </span>
                  )}
                </p>
                
                <div 
                  className="timeline-text" 
                  style={{ 
                    background: '#1a1a1a', 
                    padding: '10px', 
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                    lineHeight: '1.5',
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {formatRationale(item.rationale)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default DecisionTimeline;
