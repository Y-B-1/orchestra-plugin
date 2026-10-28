import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/portfolio", label: "Portfolio", end: false },
  { to: "/trades", label: "Trades", end: false },
  { to: "/clients", label: "Clients", end: false },
  { to: "/reports", label: "Reports", end: false },
  { to: "/settings", label: "Settings", end: false },
];

export function Sidebar() {
  return (
    <nav className="sidebar" aria-label="Primary">
      <div className="sidebar__brand">Pulse</div>
      <ul className="sidebar__list">
        {links.map((link) => (
          <li key={link.to}>
            <NavLink
              to={link.to}
              end={link.end}
              className={({ isActive }) => `sidebar__link${isActive ? " sidebar__link--active" : ""}`}
            >
              {link.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
