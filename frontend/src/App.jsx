import { QueryClient, QueryClientProvider } from "react-query";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./components/LoginPage";
import AuthCallback from "./components/AuthCallback";
import DashboardPage from "./components/DashboardPage";

const queryClient = new QueryClient();

// 인증 확인 함수
const isAuthenticated = () => {
  return !!localStorage.getItem('access_token');
};

// 보호된 라우트 컴포넌트
const ProtectedRoute = ({ children }) => {
  return isAuthenticated() ? children : <Navigate to="/login" replace />;
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          {/* 로그인 페이지 */}
          <Route 
            path="/login" 
            element={
              isAuthenticated() ? <Navigate to="/dashboard" replace /> : <LoginPage />
            } 
          />
          
          {/* OAuth 콜백 처리 */}
          <Route path="/auth/:provider/callback" element={<AuthCallback />} />
          
          {/* 대시보드 (보호된 라우트) */}
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            } 
          />
          
          {/* 루트 경로는 인증 상태에 따라 리디렉션 */}
          <Route 
            path="/" 
            element={
              <Navigate to={isAuthenticated() ? "/dashboard" : "/login"} replace />
            } 
          />
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
