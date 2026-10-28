import { Toggle } from "../components/Toggle";
import { useSettings } from "../hooks/useSettings";

export function Settings() {
  const { settings, update } = useSettings();
  return (
    <div className="page">
      <section className="panel" aria-label="Appearance">
        <div className="panel__header">
          <h2 className="panel__title">Appearance</h2>
        </div>
        <Toggle
          label="Dark theme"
          description="Use the dark color scheme."
          checked={settings.theme === "dark"}
          onChange={(on) => update("theme", on ? "dark" : "light")}
        />
      </section>
      <section className="panel" aria-label="Notifications">
        <div className="panel__header">
          <h2 className="panel__title">Notifications</h2>
        </div>
        <Toggle
          label="Email alerts"
          description="Price moves above your thresholds."
          checked={settings.emailAlerts}
          onChange={(on) => update("emailAlerts", on)}
        />
        <Toggle
          label="Push alerts"
          description="Browser notifications while Pulse is open."
          checked={settings.pushAlerts}
          onChange={(on) => update("pushAlerts", on)}
        />
        <Toggle
          label="Weekly digest"
          description="A summary email every Monday."
          checked={settings.weeklyDigest}
          onChange={(on) => update("weeklyDigest", on)}
        />
      </section>
    </div>
  );
}
