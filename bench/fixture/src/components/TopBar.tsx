import { useLocation } from "react-router-dom";
import { NotificationBell } from "./notifications/NotificationBell";
import { UserMenu } from "./UserMenu";

const titles: Record<string, string> = {
  "/": "Dashboard",
  "/portfolio": "Portfolio",
  "/trades": "Trades",
  "/clients": "Clients",
  "/reports": "Reports",
  "/settings": "Settings",
};

export function pageTitle(pathname: string): string {
  if (pathname.startsWith("/instruments/")) return "Instrument";
  return titles[pathname] ?? "Pulse";
}

export function TopBar() {
  const { pathname } = useLocation();
  return (
    <header className="topbar">
      <h1 className="topbar__title">{pageTitle(pathname)}</h1>
      <div className="topbar__actions">
        <NotificationBell />
        <UserMenu name="Dana Whitaker" />
      </div>
    </header>
  );
}
