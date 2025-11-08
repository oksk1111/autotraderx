import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

function AIMonitor() {
  const [aiStatus, setAiStatus] = useState(null);
  const [aiLogs, setAiLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    fetchAIStatus();
    fetchAILogs();
    
    // 30초마다 자동 갱신
    const interval = setInterval(() => {
      fetchAIStatus();
      fetchAILogs();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const fetchAIStatus = async () => {
    try {
      const response = await api.get('/ai/status');
      setAiStatus(response.data.data);
    } catch (error) {
      console.error('AI 상태 조회 실패:', error);
    }
  };

  const fetchAILogs = async () => {
    try {
      const response = await api.get('/ai/logs?limit=20');
      setAiLogs(response.data.data);
    } catch (error) {
      console.error('AI 로그 조회 실패:', error);
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const response = await api.post('/ai/analyze?market=KRW-BTC&use_ai=true');
      alert(`분석 완료!\n신호: ${response.data.data.signal}\n이유: ${response.data.data.reason}`);
      fetchAILogs();
    } catch (error) {
      alert('분석 실패: ' + error.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleToggleAI = async () => {
    try {
      const newState = !aiStatus?.ai_enabled;
      await api.post(`/ai/toggle?enabled=${newState}`);
      fetchAIStatus();
      alert(`AI 엔진이 ${newState ? '활성화' : '비활성화'}되었습니다`);
    } catch (error) {
      alert('AI 토글 실패: ' + error.message);
    }
  };

  const getSignalColor = (signal) => {
    switch(signal) {
      case 'buy': return 'text-green-600 font-bold';
      case 'sell': return 'text-red-600 font-bold';
      default: return 'text-gray-600';
    }
  };

  const getSignalEmoji = (signal) => {
    switch(signal) {
      case 'buy': return '📈';
      case 'sell': return '📉';
      default: return '⏸️';
    }
  };

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">🤖 AI 트레이딩 모니터</h2>
      
      {/* AI 상태 */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <h3 className="text-lg font-semibold mb-3">AI 엔진 상태</h3>
        {aiStatus ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className={`w-3 h-3 rounded-full ${aiStatus.ollama_running ? 'bg-green-500' : 'bg-red-500'}`}></span>
              <span className="font-medium">Ollama:</span>
              <span>{aiStatus.ollama_running ? '✅ 실행 중' : '❌ 중지됨'}</span>
            </div>
            <div><span className="font-medium">모델:</span> {aiStatus.model}</div>
            <div><span className="font-medium">API URL:</span> {aiStatus.api_url}</div>
            <div className="flex items-center gap-2">
              <span className="font-medium">AI 판단:</span>
              <button 
                onClick={handleToggleAI}
                className={`px-3 py-1 rounded ${aiStatus.ai_enabled ? 'bg-green-500 text-white' : 'bg-gray-300'}`}
              >
                {aiStatus.ai_enabled ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>
        ) : (
          <p>로딩 중...</p>
        )}
      </div>

      {/* 분석 버튼 */}
      <div className="mb-6">
        <button
          onClick={handleAnalyze}
          disabled={analyzing || !aiStatus?.ollama_running}
          className="w-full bg-blue-500 text-white py-3 px-4 rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          {analyzing ? '분석 중...' : '🔍 BTC 실시간 분석 실행'}
        </button>
      </div>

      {/* AI 판단 로그 */}
      <div>
        <h3 className="text-lg font-semibold mb-3">AI 판단 로그</h3>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {aiLogs.length > 0 ? (
            aiLogs.reverse().map((log, index) => (
              <div key={index} className="p-3 border rounded-lg bg-gray-50 hover:bg-gray-100">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{getSignalEmoji(log.signal)}</span>
                    <span className={getSignalColor(log.signal)}>
                      {log.signal?.toUpperCase()}
                    </span>
                    <span className="text-sm text-gray-500">{log.market}</span>
                    {log.ai_used && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">AI</span>}
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(log.timestamp).toLocaleString('ko-KR')}
                  </span>
                </div>
                <div className="text-sm text-gray-600 mb-1">
                  <span className="font-medium">가격:</span> {log.current_price?.toLocaleString()}원
                </div>
                <div className="text-sm text-gray-700">
                  <span className="font-medium">이유:</span> {log.reason}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  신뢰도: {(log.confidence * 100).toFixed(0)}%
                </div>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-4">아직 AI 판단 로그가 없습니다</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AIMonitor;
