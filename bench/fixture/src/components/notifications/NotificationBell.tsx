import { useCallback, useId, useRef, useState } from "react";
import { useClickOutside } from "../../hooks/useClickOutside";
import { useNotifications } from "../../hooks/useNotifications";
import { EmptyState, ErrorState, Loading } from "../Feedback";
import { NotificationItem } from "./NotificationItem";

export function NotificationBell({ now }: { now?: Date }) {
  const { items, unreadCount, loading, error, markRead, markAllRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(rootRef, close, open);

  const label = unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications";

  return (
    <div
      className="notifications"
      ref={rootRef}
      onKeyDown={(event) => {
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        className="notifications__trigger"
        aria-label={label}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((prev) => !prev)}
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" className="notifications__icon">
          <path d="M12 3a6 6 0 0 0-6 6v3.6l-1.7 2.9A1 1 0 0 0 5.2 17h13.6a1 1 0 0 0 .9-1.5L18 12.6V9a6 6 0 0 0-6-6Zm0 18a3 3 0 0 0 2.8-2h-5.6A3 3 0 0 0 12 21Z" />
        </svg>
        {unreadCount > 0 ? (
          <span className="notifications__count" data-testid="unread-count">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="notifications__panel" id={panelId} role="region" aria-label="Notification list">
          <div className="notifications__header">
            <h2 className="notifications__title">Notifications</h2>
            <button
              type="button"
              className="button button--small button--ghost"
              onClick={markAllRead}
              disabled={unreadCount === 0}
            >
              Mark all as read
            </button>
          </div>
          {loading ? <Loading label="Loading notifications" /> : null}
          {error ? <ErrorState error={error} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyState message="You are all caught up." /> : null}
          <ul className="notifications__list">
            {items.map((item) => (
              <NotificationItem key={item.id} item={item} now={now} onMarkRead={markRead} onNavigate={close} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
