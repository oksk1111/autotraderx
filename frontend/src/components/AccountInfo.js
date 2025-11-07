import React, { useState, useEffect } from 'react';
import { getAccountBalance } from '../services/api';

const AccountInfo = ({ refreshKey }) => {
  const [balance, setBalance] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadBalance();
  }, [refreshKey]);

  const loadBalance = async () => {
    try {
      setLoading(true);
      const response = await getAccountBalance();
      if (response.success) {
        setBalance(response.data);
      }
    } catch (error) {
      console.error('Failed to load balance:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold mb-4">계좌 정보</h2>
        <div className="text-center text-gray-400">로딩 중...</div>
      </div>
    );
  }

  const krwBalance = balance.find(b => b.currency === 'KRW');
  const totalKRW = krwBalance ? parseFloat(krwBalance.balance) : 0;

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <h2 className="text-lg font-semibold mb-4">계좌 정보</h2>
      
      <div className="mb-4 p-4 bg-slate-700 rounded-lg">
        <div className="text-sm text-gray-400 mb-1">보유 KRW</div>
        <div className="text-2xl font-bold text-blue-400">
          {totalKRW.toLocaleString()} 원
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-sm font-semibold text-gray-300 mb-2">보유 자산</div>
        {balance.filter(b => b.currency !== 'KRW' && parseFloat(b.balance) > 0).map((asset) => (
          <div key={asset.currency} className="flex justify-between items-center p-2 bg-slate-700 rounded">
            <span className="font-medium">{asset.currency}</span>
            <span className="text-sm">{parseFloat(asset.balance).toFixed(8)}</span>
          </div>
        ))}
        {balance.filter(b => b.currency !== 'KRW' && parseFloat(b.balance) > 0).length === 0 && (
          <div className="text-center text-gray-400 text-sm py-2">
            보유 자산 없음
          </div>
        )}
      </div>
    </div>
  );
};

export default AccountInfo;
