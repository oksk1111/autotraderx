import React, { useState, useEffect } from 'react';
import { getMarkets, getMultipleTickers } from '../services/api';

const MarketList = ({ selectedMarket, onSelectMarket, refreshKey }) => {
  const [markets, setMarkets] = useState([]);
  const [tickers, setTickers] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMarkets();
  }, [refreshKey]);

  const loadMarkets = async () => {
    try {
      setLoading(true);
      const response = await getMarkets();
      if (response.success) {
        const krwMarkets = response.data.filter(m => m.market.startsWith('KRW-'));
        setMarkets(krwMarkets.slice(0, 20)); // 상위 20개만

        // 티커 정보 로드
        const marketCodes = krwMarkets.slice(0, 20).map(m => m.market);
        const tickerResponse = await getMultipleTickers(marketCodes);
        if (tickerResponse.success) {
          const tickerMap = {};
          tickerResponse.data.forEach(t => {
            tickerMap[t.market] = t;
          });
          setTickers(tickerMap);
        }
      }
    } catch (error) {
      console.error('Failed to load markets:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold mb-4">마켓 목록</h2>
        <div className="text-center text-gray-400">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h2 className="text-lg font-semibold mb-4">마켓 목록</h2>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {markets.map((market) => {
          const ticker = tickers[market.market];
          const changeRate = ticker ? (ticker.signed_change_rate * 100).toFixed(2) : 0;
          const isPositive = changeRate >= 0;
          
          return (
            <div
              key={market.market}
              onClick={() => onSelectMarket(market.market)}
              className={`p-3 rounded-lg cursor-pointer transition ${
                selectedMarket === market.market
                  ? 'bg-blue-600'
                  : 'bg-slate-700 hover:bg-slate-600'
              }`}
            >
              <div className="flex justify-between items-center">
                <div>
                  <div className="font-medium">{market.korean_name}</div>
                  <div className="text-sm text-gray-400">{market.market}</div>
                </div>
                {ticker && (
                  <div className="text-right">
                    <div className="font-medium">
                      {ticker.trade_price.toLocaleString()}
                    </div>
                    <div className={`text-sm ${isPositive ? 'text-red-400' : 'text-blue-400'}`}>
                      {isPositive ? '+' : ''}{changeRate}%
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MarketList;
