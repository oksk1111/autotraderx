import React, { useState, useEffect } from 'react';
import { getPositions } from '../services/api';

const PositionsPanel = ({ refreshKey }) => {
  const [positions, setPositions] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPositions();
  }, [refreshKey]);

  const loadPositions = async () => {
    try {
      setLoading(true);
      const response = await getPositions();
      if (response.success) {
        setPositions(response.data);
      }
    } catch (error) {
      console.error('Failed to load positions:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold mb-4">보유 포지션</h2>
        <div className="text-center text-gray-400">로딩 중...</div>
      </div>
    );
  }

  const positionList = Object.entries(positions);

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h2 className="text-lg font-semibold mb-4">보유 포지션</h2>
      
      {positionList.length === 0 ? (
        <div className="text-center text-gray-400 py-8">
          보유 중인 포지션이 없습니다
        </div>
      ) : (
        <div className="space-y-4">
          {positionList.map(([market, position]) => (
            <div key={market} className="bg-slate-700 p-4 rounded-lg">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <div className="font-semibold text-lg">{market}</div>
                  <div className="text-sm text-gray-400">
                    평균 매수가: {position.avg_buy_price?.toLocaleString()} KRW
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-gray-400">수량:</span>
                  <span className="ml-2 font-medium">{position.volume?.toFixed(8)}</span>
                </div>
                <div>
                  <span className="text-gray-400">주문ID:</span>
                  <span className="ml-2 font-medium text-xs">{position.order_id?.substring(0, 8)}...</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PositionsPanel;
