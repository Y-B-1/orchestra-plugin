import { useEffect, useRef, type ReactNode } from "react";

interface DrawerProps {
  /** Accessible name of the dialog, for example "Client details". */
  label: string;
  title: ReactNode;
  onClose: () => void;
  closeLabel?: string;
  subtitle?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * A panel that slides in from the right edge. Escape closes it, and focus moves
 * to the close button on open and back to the previously focused element on close.
 */
export function Drawer({ label, title, onClose, closeLabel = "Close", subtitle, footer, children }: DrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    return () => previous?.focus();
  }, []);

  return (
    <aside className="drawer" role="dialog" aria-label={label}>
      <header className="drawer__header">
        <div className="drawer__heading">
          <h2 className="drawer__title">{title}</h2>
          {subtitle ? <p className="drawer__subtitle">{subtitle}</p> : null}
        </div>
        <button ref={closeRef} type="button" className="button button--ghost" onClick={onClose} aria-label={closeLabel}>
          Close
        </button>
      </header>
      <div className="drawer__body">{children}</div>
      {footer ? <footer className="drawer__footer">{footer}</footer> : null}
    </aside>
  );
}
