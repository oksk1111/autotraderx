import React, { useState, useEffect } from 'react';
import { analyzeMarket, executeTrade } from '../services/api';

const TradingPanel = ({ market, refreshKey, onTradeComplete }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);

  useEffect(() => {
    if (market) {
      loadAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [market, refreshKey]);

  const loadAnalysis = async () => {
    try {
      setLoading(true);
      const response = await analyzeMarket(market);
      if (response.success) {
        setAnalysis(response.data);
      }
    } catch (error) {
      console.error('Failed to analyze market:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTrade = async (signal) => {
    if (!window.confirm(`${signal === 'buy' ? '매수' : '매도'}를 실행하시겠습니까?`)) {
      return;
    }

    try {
      setExecuting(true);
      const response = await executeTrade(market, signal);
      if (response.success) {
        alert('거래가 성공적으로 실행되었습니다!');
        onTradeComplete();
      }
    } catch (error) {
      alert(`거래 실행 실패: ${error.message}`);
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold mb-4">매매 분석</h2>
        <div className="text-center text-gray-400">분석 중...</div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold mb-4">매매 분석</h2>
        <div className="text-center text-gray-400">마켓을 선택하세요</div>
      </div>
    );
  }

  const getSignalColor = (signal) => {
    if (signal === 'buy') return 'text-green-400';
    if (signal === 'sell') return 'text-red-400';
    return 'text-gray-400';
  };

  const getSignalText = (signal) => {
    if (signal === 'buy') return '매수 신호';
    if (signal === 'sell') return '매도 신호';
    return '관망';
  };

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h2 className="text-lg font-semibold mb-4">매매 분석 - {market}</h2>

      {/* Signal */}
      <div className="mb-6 p-4 bg-slate-700 rounded-lg">
        <div className="text-sm text-gray-400 mb-2">신호</div>
        <div className={`text-2xl font-bold ${getSignalColor(analysis.signal)}`}>
          {getSignalText(analysis.signal)}
        </div>
        <div className="text-sm text-gray-400 mt-2">
          신뢰도: {(analysis.confidence * 100).toFixed(0)}%
        </div>
      </div>

      {/* Current Price */}
      <div className="mb-6">
        <div className="text-sm text-gray-400 mb-2">현재가</div>
        <div className="text-xl font-bold">
          {analysis.current_price?.toLocaleString()} KRW
        </div>
      </div>

      {/* Reason */}
      <div className="mb-6">
        <div className="text-sm text-gray-400 mb-2">분석 근거</div>
        <div className="text-sm bg-slate-700 p-3 rounded">
          {analysis.reason}
        </div>
      </div>

      {/* Indicators */}
      {analysis.indicators && (
        <div className="mb-6">
          <div className="text-sm text-gray-400 mb-2">기술적 지표</div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-700 p-3 rounded">
              <div className="text-xs text-gray-400">RSI</div>
              <div className="font-medium">{analysis.indicators.rsi?.toFixed(2)}</div>
            </div>
            <div className="bg-slate-700 p-3 rounded">
              <div className="text-xs text-gray-400">MFI</div>
              <div className="font-medium">{analysis.indicators.mfi?.toFixed(2)}</div>
            </div>
            <div className="bg-slate-700 p-3 rounded">
              <div className="text-xs text-gray-400">MACD</div>
              <div className="font-medium">{analysis.indicators.macd?.macd?.toFixed(2)}</div>
            </div>
            <div className="bg-slate-700 p-3 rounded">
              <div className="text-xs text-gray-400">추세</div>
              <div className="font-medium">{analysis.indicators.trend}</div>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => handleTrade('buy')}
          disabled={executing}
          className="py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-medium transition"
        >
          {executing ? '실행 중...' : '매수'}
        </button>
        <button
          onClick={() => handleTrade('sell')}
          disabled={executing}
          className="py-3 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-medium transition"
        >
          {executing ? '실행 중...' : '매도'}
        </button>
      </div>
    </div>
  );
};

export default TradingPanel;
