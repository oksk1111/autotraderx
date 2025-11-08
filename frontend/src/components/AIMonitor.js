import React, { useState, useEffect } from 'react';
import apiClient, { getAIModels, selectAIModel, pullAIModel } from '../services/api';

function AIMonitor() {
  const [aiStatus, setAiStatus] = useState(null);
  const [aiLogs, setAiLogs] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [models, setModels] = useState({ models: [], current_model: '', recommended_models: [] });
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    fetchAIStatus();
    fetchAILogs();
    fetchModels();
    
    // 30초마다 자동 갱신
    const interval = setInterval(() => {
      fetchAIStatus();
      fetchAILogs();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const fetchAIStatus = async () => {
    try {
      const response = await apiClient.get('/api/v1/ai/status');
      setAiStatus(response.data.data);
    } catch (error) {
      console.error('AI 상태 조회 실패:', error);
      if (error.code === 'ECONNABORTED') {
        console.warn('API 응답 시간 초과 - 백엔드가 시작 중일 수 있습니다');
      }
    }
  };

  const fetchAILogs = async () => {
    try {
      const response = await apiClient.get('/api/v1/ai/logs?limit=20');
      setAiLogs(response.data.data || []);
    } catch (error) {
      console.error('AI 로그 조회 실패:', error);
      if (error.code === 'ECONNABORTED') {
        console.warn('API 응답 시간 초과 - 백엔드가 시작 중일 수 있습니다');
      }
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const response = await apiClient.post('/api/v1/ai/analyze?market=KRW-BTC&use_ai=true');
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
      await apiClient.post(`/api/v1/ai/toggle?enabled=${newState}`);
      fetchAIStatus();
      alert(`AI 엔진이 ${newState ? '활성화' : '비활성화'}되었습니다`);
    } catch (error) {
      alert('AI 토글 실패: ' + error.message);
    }
  };

  const fetchModels = async () => {
    try {
      const response = await getAIModels();
      if (response.success) {
        setModels(response.data);
      }
    } catch (error) {
      console.error('모델 목록 조회 실패:', error);
    }
  };

  const handleSelectModel = async (modelName) => {
    try {
      const response = await selectAIModel(modelName);
      if (response.success) {
        alert(`모델이 ${modelName}으로 변경되었습니다`);
        fetchAIStatus();
        fetchModels();
        setShowModelSelector(false);
      }
    } catch (error) {
      alert('모델 변경 실패: ' + error.message);
    }
  };

  const handlePullModel = async (modelName) => {
    if (!window.confirm(`${modelName} 모델을 다운로드하시겠습니까?\n시간이 오래 걸릴 수 있습니다.`)) {
      return;
    }

    try {
      setDownloading(true);
      const response = await pullAIModel(modelName);
      if (response.success) {
        alert(`${modelName} 모델 다운로드가 완료되었습니다`);
        fetchModels();
      }
    } catch (error) {
      alert('모델 다운로드 실패: ' + error.message);
    } finally {
      setDownloading(false);
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
    <div className="p-6 bg-white rounded-lg shadow-md text-gray-900">
      <h2 className="text-2xl font-bold mb-4 text-gray-900">🤖 AI 트레이딩 모니터</h2>
      
      {/* AI 상태 */}
      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <h3 className="text-lg font-semibold mb-3 text-gray-900">AI 엔진 상태</h3>
        {aiStatus ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className={`w-3 h-3 rounded-full ${aiStatus.ollama_running ? 'bg-green-500' : 'bg-red-500'}`}></span>
              <span className="font-medium text-gray-900">Ollama:</span>
              <span className="text-gray-900">{aiStatus.ollama_running ? '✅ 실행 중' : '❌ 중지됨'}</span>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium text-gray-900">모델:</span> <span className="text-gray-900">{aiStatus.model}</span>
              </div>
              <button
                onClick={() => setShowModelSelector(!showModelSelector)}
                className="text-sm text-blue-600 hover:text-blue-800 underline"
              >
                {showModelSelector ? '닫기' : '모델 변경'}
              </button>
            </div>
            <div className="text-gray-900"><span className="font-medium">API URL:</span> {aiStatus.api_url}</div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900">AI 판단:</span>
              <button 
                onClick={handleToggleAI}
                className={`px-3 py-1 rounded ${aiStatus.ai_enabled ? 'bg-green-500 text-white' : 'bg-gray-300'}`}
              >
                {aiStatus.ai_enabled ? 'ON' : 'OFF'}
              </button>
            </div>
          </div>
        ) : (
          <p className="text-gray-900">로딩 중...</p>
        )}
      </div>

      {/* 모델 선택기 */}
      {showModelSelector && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="text-lg font-semibold mb-3 text-gray-900">🤖 LLM 모델 선택</h3>
          
          {/* 설치된 모델 */}
          <div className="mb-4">
            <h4 className="font-medium mb-2 text-gray-900">설치된 모델 ({models.models.length}개)</h4>
            {models.models.length > 0 ? (
              <div className="space-y-2">
                {models.models.map((model) => (
                  <div key={model.name} className="flex items-center justify-between p-2 bg-white rounded border">
                    <div>
                      <span className="font-medium text-gray-900">{model.name}</span>
                      <span className="text-xs text-gray-500 ml-2">
                        ({(model.size / 1024 / 1024 / 1024).toFixed(2)} GB)
                      </span>
                      {model.name === models.current_model && (
                        <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-1 rounded">사용 중</span>
                      )}
                    </div>
                    {model.name !== models.current_model && (
                      <button
                        onClick={() => handleSelectModel(model.name)}
                        className="text-sm bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                      >
                        선택
                      </button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-900 text-sm">설치된 모델이 없습니다</p>
            )}
          </div>

          {/* 추천 모델 */}
          <div>
            <h4 className="font-medium mb-2 text-gray-900">📚 추천 모델 (다운로드 필요)</h4>
            <div className="space-y-2">
              {models.recommended_models.map((model) => (
                <div key={model.name} className="p-3 bg-white rounded border">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="font-medium text-gray-900">{model.name}</div>
                      <div className="text-sm text-gray-600">{model.description}</div>
                      <div className="text-xs text-gray-500">용도: {model.use_case}</div>
                    </div>
                    <button
                      onClick={() => handlePullModel(model.name)}
                      disabled={downloading || models.models.some(m => m.name === model.name)}
                      className="text-sm bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed whitespace-nowrap ml-2"
                    >
                      {models.models.some(m => m.name === model.name) ? '설치됨' : downloading ? '다운로드 중...' : '다운로드'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

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
        <h3 className="text-lg font-semibold mb-3 text-gray-900">AI 판단 로그</h3>
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
                    <span className="text-sm text-gray-600">{log.market}</span>
                    {log.ai_used && <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded">AI</span>}
                  </div>
                  <span className="text-xs text-gray-500">
                    {new Date(log.timestamp).toLocaleString('ko-KR')}
                  </span>
                </div>
                <div className="text-sm text-gray-700 mb-1">
                  <span className="font-medium">가격:</span> {log.current_price?.toLocaleString()}원
                </div>
                <div className="text-sm text-gray-800">
                  <span className="font-medium">이유:</span> {log.reason}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  신뢰도: {(log.confidence * 100).toFixed(0)}%
                </div>
              </div>
            ))
          ) : (
            <p className="text-gray-700 text-center py-4">아직 AI 판단 로그가 없습니다</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AIMonitor;
