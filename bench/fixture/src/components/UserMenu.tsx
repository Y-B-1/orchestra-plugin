import { useState } from "react";
import { Link } from "react-router-dom";
import { initials } from "../utils/format";

export function UserMenu({ name }: { name: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="user-menu">
      <button
        type="button"
        className="user-menu__trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="user-menu__avatar" aria-hidden="true">
          {initials(name)}
        </span>
        <span>{name}</span>
      </button>
      {open ? (
        <ul className="user-menu__list" role="menu">
          <li role="none">
            <Link role="menuitem" to="/settings" onClick={() => setOpen(false)}>
              Settings
            </Link>
          </li>
          <li role="none">
            <button type="button" role="menuitem" onClick={() => setOpen(false)}>
              Sign out
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}
