import { Link } from "react-router-dom";
import type { AppNotification, NotificationKind } from "../../types";
import { formatRelative } from "../../utils/dates";

const kindLabels: Record<NotificationKind, string> = {
  trade: "Trade",
  report: "Report",
  client: "Client",
  system: "System",
};

interface NotificationItemProps {
  item: AppNotification;
  now?: Date;
  onMarkRead: (id: string) => void;
  onNavigate: () => void;
}

export function NotificationItem({ item, now, onMarkRead, onNavigate }: NotificationItemProps) {
  return (
    <li className={`notification${item.read ? "" : " notification--unread"}`}>
      <div className="notification__meta">
        <span className={`notification__kind notification__kind--${item.kind}`}>{kindLabels[item.kind]}</span>
        <time dateTime={item.createdAt}>{formatRelative(item.createdAt, now)}</time>
      </div>
      <p className="notification__title">
        {item.link ? (
          <Link
            to={item.link}
            onClick={() => {
              onMarkRead(item.id);
              onNavigate();
            }}
          >
            {item.title}
          </Link>
        ) : (
          item.title
        )}
      </p>
      <p className="notification__body">{item.body}</p>
      {item.read ? null : (
        <button
          type="button"
          className="notification__mark"
          onClick={() => onMarkRead(item.id)}
          aria-label={`Mark "${item.title}" as read`}
        >
          Mark as read
        </button>
      )}
    </li>
  );
}
