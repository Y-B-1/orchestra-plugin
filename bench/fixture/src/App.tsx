import { Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Clients } from "./pages/Clients";
import { Dashboard } from "./pages/Dashboard";
import { InstrumentDetail } from "./pages/InstrumentDetail";
import { Portfolio } from "./pages/Portfolio";
import { Reports } from "./pages/Reports";
import { Settings } from "./pages/Settings";
import { Trades } from "./pages/Trades";

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="trades" element={<Trades />} />
        <Route path="instruments/:symbol" element={<InstrumentDetail />} />
        <Route path="clients" element={<Clients />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<p className="feedback feedback--empty">Page not found.</p>} />
      </Route>
    </Routes>
  );
}
