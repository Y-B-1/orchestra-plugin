import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { NotificationsProvider } from "./hooks/useNotifications";
import { SettingsProvider } from "./hooks/useSettings";
import "./styles/theme.css";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SettingsProvider>
        <NotificationsProvider>
          <App />
        </NotificationsProvider>
      </SettingsProvider>
    </BrowserRouter>
  </StrictMode>,
);
