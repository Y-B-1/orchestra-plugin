import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Settings } from "../types";
import { readJson, writeJson } from "../utils/storage";

export const SETTINGS_KEY = "pulse.settings";

export const defaultSettings: Settings = {
  theme: "light",
  emailAlerts: true,
  pushAlerts: false,
  weeklyDigest: true,
};

interface SettingsContextValue {
  settings: Settings;
  update: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(() => readJson(SETTINGS_KEY, defaultSettings));

  useEffect(() => {
    writeJson(SETTINGS_KEY, settings);
    document.documentElement.dataset.theme = settings.theme;
  }, [settings]);

  const value = useMemo<SettingsContextValue>(
    () => ({
      settings,
      update: (key, next) => setSettings((prev) => ({ ...prev, [key]: next })),
    }),
    [settings],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used inside SettingsProvider");
  return ctx;
}
