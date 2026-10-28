import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SETTINGS_KEY, SettingsProvider } from "../hooks/useSettings";
import { Settings } from "./Settings";

function renderSettings() {
  return render(
    <SettingsProvider>
      <Settings />
    </SettingsProvider>,
  );
}

describe("Settings page", () => {

  it("persists a change to localStorage", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("switch", { name: "Push alerts" }));
    expect(JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "{}").pushAlerts).toBe(true);
  });

  it("applies the dark theme to the document", () => {
    renderSettings();
    fireEvent.click(screen.getByRole("switch", { name: "Dark theme" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
