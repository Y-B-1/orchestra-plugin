import data from "../data/notifications.json";
import type { AppNotification } from "../types";
import { delay } from "./client";

const notifications = data as AppNotification[];

/** Notifications for the signed-in user, newest first. */
export async function fetchNotifications(): Promise<AppNotification[]> {
  const sorted = [...notifications].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return delay(sorted.map((row) => ({ ...row })));
}
