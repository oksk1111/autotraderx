import React, { useState, useEffect } from 'react';
import MarketList from '../components/MarketList';
import TradingPanel from '../components/TradingPanel';
import PositionsPanel from '../components/PositionsPanel';
import AccountInfo from '../components/AccountInfo';
import AIMonitor from '../components/AIMonitor';

const Dashboard = () => {
  const [selectedMarket, setSelectedMarket] = useState('KRW-BTC');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-gray-100">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-blue-400">AutoTraderX</h1>
            <p className="text-sm text-gray-400">업비트 자동 매매 시스템</p>
          </div>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition"
          >
            새로고침
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-6">
        {/* AI Monitor - Full Width */}
        <div className="mb-6">
          <AIMonitor />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Account & Market List */}
          <div className="space-y-6">
            <AccountInfo refreshKey={refreshKey} />
            <MarketList 
              selectedMarket={selectedMarket}
              onSelectMarket={setSelectedMarket}
              refreshKey={refreshKey}
            />
          </div>

          {/* Middle Column - Trading Panel */}
          <div>
            <TradingPanel 
              market={selectedMarket}
              refreshKey={refreshKey}
              onTradeComplete={handleRefresh}
            />
          </div>

          {/* Right Column - Positions */}
          <div>
            <PositionsPanel refreshKey={refreshKey} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
