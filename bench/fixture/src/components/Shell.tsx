import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function Shell() {
  return (
    <div className="shell">
      <Sidebar />
      <div className="shell__main">
        <TopBar />
        <main className="shell__content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
