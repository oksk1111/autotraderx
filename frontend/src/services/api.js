import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 200000, // 200초 (AI 분석은 최대 180초 소요 가능)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Market APIs
export const getMarkets = async () => {
  const response = await apiClient.get('/api/v1/market/markets');
  return response.data;
};

export const getTicker = async (market) => {
  const response = await apiClient.get(`/api/v1/market/ticker/${market}`);
  return response.data;
};

export const getMultipleTickers = async (markets) => {
  const response = await apiClient.get(`/api/v1/market/tickers?markets=${markets.join(',')}`);
  return response.data;
};

export const getCandles = async (market, unit = 'minutes/5', count = 200) => {
  const response = await apiClient.get(`/api/v1/market/candles/${market}`, {
    params: { unit, count }
  });
  return response.data;
};

// Trading APIs
export const analyzeMarket = async (market, interval = 'minutes/5', count = 200) => {
  const response = await apiClient.post('/api/v1/trading/analyze', {
    market,
    interval,
    count
  });
  return response.data;
};

export const executeTrade = async (market, signal, amount = null) => {
  const response = await apiClient.post('/api/v1/trading/execute', {
    market,
    signal,
    amount
  });
  return response.data;
};

export const getPositions = async () => {
  const response = await apiClient.get('/api/v1/trading/positions');
  return response.data;
};

export const getTradingStatus = async () => {
  const response = await apiClient.get('/api/v1/trading/status');
  return response.data;
};

// Account APIs
export const getAccountBalance = async () => {
  const response = await apiClient.get('/api/v1/account/balance');
  return response.data;
};

export const getOrders = async (state = 'wait', market = null) => {
  const params = { state };
  if (market) params.market = market;
  const response = await apiClient.get('/api/v1/account/orders', { params });
  return response.data;
};

// AI APIs
export const getAIModels = async () => {
  const response = await apiClient.get('/api/v1/ai/models');
  return response.data;
};

export const selectAIModel = async (modelName) => {
  const response = await apiClient.post(`/api/v1/ai/models/select?model_name=${modelName}`);
  return response.data;
};

export const pullAIModel = async (modelName) => {
  const response = await apiClient.post(`/api/v1/ai/models/pull?model_name=${modelName}`);
  return response.data;
};

export default apiClient;
