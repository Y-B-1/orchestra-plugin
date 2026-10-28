import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface TabItem {
  id: string;
  label: string;
  /** Optional count shown after the label, such as the number of notes. */
  badge?: number;
  render: () => ReactNode;
}

interface TabsProps {
  /** Accessible name of the tab list. */
  label: string;
  tabs: readonly TabItem[];
  /** Controlled selection; omit to let the component track it. */
  value?: string;
  defaultValue?: string;
  onChange?: (id: string) => void;
  className?: string;
}

/** WAI-ARIA tabs: arrow keys, Home and End move between tabs; only the active panel renders. */
export function Tabs({ label, tabs, value, defaultValue, onChange, className }: TabsProps) {
  const baseId = useId();
  const [ownValue, setOwnValue] = useState(defaultValue ?? tabs[0]?.id ?? "");
  const active = value ?? ownValue;
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  function select(id: string) {
    if (value === undefined) setOwnValue(id);
    onChange?.(id);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    const tab = tabs[next];
    if (!tab) return;
    select(tab.id);
    buttons.current[next]?.focus();
  }

  const current = tabs.find((tab) => tab.id === active) ?? tabs[0];

  return (
    <div className={`tabs${className ? ` ${className}` : ""}`}>
      <div className="tabs__list" role="tablist" aria-label={label}>
        {tabs.map((tab, index) => {
          const selected = tab.id === current?.id;
          return (
            <button
              key={tab.id}
              ref={(node) => {
                buttons.current[index] = node;
              }}
              id={`${baseId}-tab-${tab.id}`}
              type="button"
              role="tab"
              className={`tabs__tab${selected ? " tabs__tab--active" : ""}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => select(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
            >
              {tab.label}
              {tab.badge !== undefined ? <span className="tabs__badge">{tab.badge}</span> : null}
            </button>
          );
        })}
      </div>
      {current ? (
        <div
          id={`${baseId}-panel-${current.id}`}
          role="tabpanel"
          className="tabs__panel"
          aria-labelledby={`${baseId}-tab-${current.id}`}
          tabIndex={0}
        >
          {current.render()}
        </div>
      ) : null}
    </div>
  );
}
