import { QueryClient, QueryClientProvider } from "react-query";
import DashboardPage from "./components/DashboardPage";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>
  );
}

export default App;
