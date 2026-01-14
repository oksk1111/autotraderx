import { QueryClient, QueryClientProvider } from "react-query";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./components/LoginPage";
import AuthCallback from "./components/AuthCallback";
import DashboardPage from "./components/DashboardPage";

const queryClient = new QueryClient();

// 인증 확인 함수 (항상 true 반환하여 로그인 우회)
const isAuthenticated = () => {
  // return !!localStorage.getItem('access_token');
  return true; 
};

// 보호된 라우트 컴포넌트 (사실상 기능 해제)
const ProtectedRoute = ({ children }) => {
  return children;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          {/* 로그인 페이지 (사용 안 함, 접근 시 대시보드로 이동) */}
          <Route path="/login" element={<Navigate to="/dashboard" replace />} />
          
          {/* OAuth 콜백 처리 (사용 안 함) */}
          {/* <Route path="/auth/:provider/callback" element={<AuthCallback />} /> */}
          
          {/* 대시보드 */}
          <Route path="/dashboard" element={<DashboardPage />} />
          
          {/* 루트 경로를 대시보드로 고정 */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
