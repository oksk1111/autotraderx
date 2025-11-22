import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import axios from "axios";

const api = axios.create({ baseURL: "/api" });

const CYCLE_PRESETS = [
  { label: "1분 (공격적)", value: 60, color: "#f44336" },
  { label: "3분 (빠른 대응)", value: 180, color: "#ff9800" },
  { label: "5분 (권장)", value: 300, color: "#4caf50" },
  { label: "10분 (보수적)", value: 600, color: "#2196f3" },
  { label: "30분", value: 1800, color: "#9e9e9e" },
  { label: "1시간", value: 3600, color: "#9e9e9e" },
];

function TradingConfigPanel() {
  const queryClient = useQueryClient();
  const [customCycle, setCustomCycle] = useState("");

  const { data: config, isLoading } = useQuery(
    ["config"],
    async () => {
      const { data } = await api.get("/config/");
      return data;
    },
    { refetchInterval: 10000 }
  );

  const updateMutation = useMutation(
    async (newConfig) => {
      const { data } = await api.put("/config/", newConfig);
      return data;
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["config"]);
      },
    }
  );

  const handlePresetClick = (seconds) => {
    if (config) {
      updateMutation.mutate({ ...config, trading_cycle_seconds: seconds });
    }
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    const seconds = parseInt(customCycle, 10);
    if (seconds >= 10 && seconds <= 7200 && config) {
      updateMutation.mutate({ ...config, trading_cycle_seconds: seconds });
      setCustomCycle("");
    }
  };

  const handleToggleActive = () => {
    if (config) {
      updateMutation.mutate({ ...config, is_active: !config.is_active });
    }
  };

  const formatCycleDisplay = (seconds) => {
    if (seconds < 60) return `${seconds}초`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}분`;
    return `${Math.floor(seconds / 3600)}시간`;
  };

  if (isLoading) {
    return (
      <div style={{ padding: "20px", textAlign: "center" }}>
        <p style={{ color: "#888" }}>설정 로딩중...</p>
      </div>
    );
  }

  const currentCycle = config?.trading_cycle_seconds || 300;
  const isActive = config?.is_active || false;

  return (
    <div
      style={{
        backgroundColor: "#1a1a1a",
        border: "1px solid #333",
        borderRadius: "8px",
        padding: "20px",
        marginBottom: "20px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: "18px", color: "#fff" }}>
            ⚙️ 매매 설정
          </h2>
          <p style={{ margin: "5px 0 0 0", fontSize: "14px", color: "#888" }}>
            현재 주기: <strong style={{ color: "#4caf50" }}>{formatCycleDisplay(currentCycle)}</strong>
          </p>
        </div>
        <button
          onClick={handleToggleActive}
          style={{
            padding: "10px 20px",
            backgroundColor: isActive ? "#f44336" : "#4caf50",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontSize: "14px",
            fontWeight: "bold",
          }}
        >
          {isActive ? "🛑 중단" : "▶️ 시작"}
        </button>
      </div>

      <div style={{ marginBottom: "15px" }}>
        <h3 style={{ fontSize: "14px", color: "#aaa", marginBottom: "10px" }}>
          프리셋 주기
        </h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
            gap: "10px",
          }}
        >
          {CYCLE_PRESETS.map((preset) => (
            <button
              key={preset.value}
              onClick={() => handlePresetClick(preset.value)}
              disabled={updateMutation.isLoading}
              style={{
                padding: "12px",
                backgroundColor:
                  currentCycle === preset.value ? preset.color : "#2a2a2a",
                color: "#fff",
                border:
                  currentCycle === preset.value
                    ? `2px solid ${preset.color}`
                    : "1px solid #444",
                borderRadius: "6px",
                cursor: updateMutation.isLoading ? "wait" : "pointer",
                fontSize: "13px",
                fontWeight: currentCycle === preset.value ? "bold" : "normal",
                transition: "all 0.2s",
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: "14px", color: "#aaa", marginBottom: "10px" }}>
          커스텀 주기 (10초 ~ 2시간)
        </h3>
        <form
          onSubmit={handleCustomSubmit}
          style={{ display: "flex", gap: "10px" }}
        >
          <input
            type="number"
            value={customCycle}
            onChange={(e) => setCustomCycle(e.target.value)}
            placeholder="초 단위 입력 (예: 120)"
            min="10"
            max="7200"
            style={{
              flex: 1,
              padding: "10px",
              backgroundColor: "#2a2a2a",
              border: "1px solid #444",
              borderRadius: "6px",
              color: "#fff",
              fontSize: "14px",
            }}
          />
          <button
            type="submit"
            disabled={updateMutation.isLoading}
            style={{
              padding: "10px 20px",
              backgroundColor: "#2196f3",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              cursor: updateMutation.isLoading ? "wait" : "pointer",
              fontSize: "14px",
              fontWeight: "bold",
            }}
          >
            적용
          </button>
        </form>
      </div>

      {updateMutation.isError && (
        <p style={{ color: "#f44336", marginTop: "10px", fontSize: "13px" }}>
          ⚠️ 설정 업데이트 실패
        </p>
      )}
      {updateMutation.isSuccess && (
        <p style={{ color: "#4caf50", marginTop: "10px", fontSize: "13px" }}>
          ✅ 설정이 업데이트되었습니다
        </p>
      )}
    </div>
  );
}

export default TradingConfigPanel;
