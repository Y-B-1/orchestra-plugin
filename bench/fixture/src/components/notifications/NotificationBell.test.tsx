import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";
import { latency } from "../../api";
import { NotificationsProvider, READ_NOTIFICATIONS_KEY } from "../../hooks/useNotifications";
import { NotificationBell } from "./NotificationBell";

beforeAll(() => {
  latency.ms = 0;
});

function renderBell() {
  return render(
    <MemoryRouter>
      <NotificationsProvider>
        <NotificationBell now={new Date("2026-10-28T08:00:00Z")} />
      </NotificationsProvider>
    </MemoryRouter>,
  );
}

describe("NotificationBell", () => {
  it("shows the unread count and lists notifications when opened", async () => {
    renderBell();
    expect(await screen.findByRole("button", { name: "Notifications, 3 unread" })).toBeInTheDocument();
    expect(screen.getByTestId("unread-count")).toHaveTextContent("3");
    cleanup();
    renderBell();
    fireEvent.click(await screen.findByRole("button", { name: /Notifications, 3 unread/ }));
    expect(screen.getByRole("region", { name: "Notification list" })).toBeInTheDocument();
    expect(screen.getByText("Large fill on NVDA")).toBeInTheDocument();
    expect(screen.getByText("12 hours ago")).toBeInTheDocument();
  });

  it("marks a single notification as read", async () => {
    renderBell();
    fireEvent.click(await screen.findByRole("button", { name: /Notifications, 3 unread/ }));
    fireEvent.click(screen.getByRole("button", { name: 'Mark "Rates desk summary failed" as read' }));
    expect(screen.getByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();
  });

  it("saves every notification as read on mark all", async () => {
    renderBell();
    fireEvent.click(await screen.findByRole("button", { name: /Notifications, 3 unread/ }));
    fireEvent.click(screen.getByRole("button", { name: "Mark all as read" }));
    const saved = JSON.parse(localStorage.getItem(READ_NOTIFICATIONS_KEY) ?? "[]") as string[];
    expect(saved).toEqual(expect.arrayContaining(["n-108", "n-107", "n-106"]));
  });
});
