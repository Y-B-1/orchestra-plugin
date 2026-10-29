// Task G, the sign-in flow: one test file section per rule. Test names start with the ask id.
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, waitFor, within } from "@testing-library/react";
import {
  ACCOUNTS,
  closeApp,
  MESSAGE,
  onPage,
  openApp,
  primaryNav,
  seedSession,
  SESSION_KEY,
  SLOW,
  signOut,
  submitSignIn,
} from "./helpers";

beforeEach(() => localStorage.clear());
afterEach(closeApp);

const NEW_PASSWORD = "a-much-longer-one";

async function fillNewPassword(s: Awaited<ReturnType<typeof openApp>>, password: string, confirmation: string) {
  fireEvent.change(s.getByLabelText("New password"), { target: { value: password } });
  fireEvent.change(s.getByLabelText("Confirm new password"), { target: { value: confirmation } });
  fireEvent.click(s.getByRole("button", { name: "Save password" }));
}

describe("medium: sign-in", () => {
  it("G1 other addresses send a signed-out visitor to /sign-in, and signing in lands on the dashboard", async () => {
    const s = await openApp("/trades");
    expect(await s.findByRole("heading", { name: "Sign in" }, SLOW)).toBeInTheDocument();
    expect(window.location.pathname).toBe("/sign-in");
    expect(s.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
    submitSignIn(ACCOUNTS.dana.email, ACCOUNTS.dana.password);
    await onPage("Dashboard");
    expect(window.location.pathname).toBe("/");
    expect(within(primaryNav()).getByRole("link", { name: "Trades" })).toBeInTheDocument();
  });

  it("G1 the button shows Signing in... and is disabled while the request runs, and Enter submits the form", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    fireEvent.change(s.getByLabelText("Email"), { target: { value: ACCOUNTS.owen.email } });
    fireEvent.change(s.getByLabelText("Password"), { target: { value: ACCOUNTS.owen.password } });
    // jsdom has no implicit submission, so Enter is the form's submit event.
    fireEvent.submit(s.getByLabelText("Password").closest("form")!);
    const busy = await s.findByRole("button", { name: "Signing in..." });
    expect(busy).toBeDisabled();
    await onPage("Dashboard");
  });

  it("G2 no shared password: demo and other people's passwords never work", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    const tries: [string, string][] = [
      [ACCOUNTS.dana.email, "demo"],
      [ACCOUNTS.marc.email, "demo"],
      [ACCOUNTS.ines.email, "Demo1234"],
      [ACCOUNTS.dana.email, ACCOUNTS.marc.password],
      [ACCOUNTS.owen.email, ACCOUNTS.dana.password],
      [ACCOUNTS.ines.email, ACCOUNTS.owen.password],
    ];
    for (const [email, password] of tries) {
      submitSignIn(email, password);
      expect(await s.findByRole("alert", {}, SLOW)).toHaveTextContent(MESSAGE);
      await waitFor(() => expect(s.getByRole("button", { name: "Sign in" })).toBeEnabled(), SLOW);
      expect(s.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
      expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    }
  });

  it("G3 there is no claim page and no link to one", async () => {
    const signedOut = await openApp("/sign-in");
    await signedOut.findByRole("heading", { name: "Sign in" }, SLOW);
    expect(signedOut.queryByText(/claim/i)).not.toBeInTheDocument();
    closeApp();
    seedSession(ACCOUNTS.dana.email);
    const s = await openApp("/claim");
    expect(await s.findByText("Page not found.", {}, SLOW)).toBeInTheDocument();
    const anchors = Array.from(document.querySelectorAll("a"));
    expect(anchors.some((a) => /claim/i.test(`${a.getAttribute("href")} ${a.textContent}`))).toBe(false);
    fireEvent.click(s.getByRole("button", { name: "Dana Whitaker" }));
    expect(s.queryByText(/claim/i)).not.toBeInTheDocument();
  });

  it("G4 people with a saved session stay signed in and are not asked for a new password", async () => {
    seedSession(ACCOUNTS.marc.email);
    const s = await openApp("/");
    await onPage("Dashboard");
    expect(s.queryByRole("heading", { name: "Choose a new password" })).not.toBeInTheDocument();
    expect(s.getByRole("button", { name: "Marc Ellery" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("G4 signing in saves the session under pulse.session and a reload keeps you in", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    submitSignIn(ACCOUNTS.owen.email, ACCOUNTS.owen.password);
    await onPage("Dashboard");
    expect(JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null")).toBe(ACCOUNTS.owen.email);
    closeApp();
    await openApp("/trades");
    await onPage("Trades");
    expect(window.location.pathname).toBe("/trades");
  });

  it("G4 Sign out removes the session and goes to /sign-in", async () => {
    seedSession(ACCOUNTS.dana.email);
    await openApp("/");
    await onPage("Dashboard");
    await signOut("Dana Whitaker");
    expect(window.location.pathname).toBe("/sign-in");
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
    closeApp();
    const again = await openApp("/portfolio");
    expect(await again.findByRole("heading", { name: "Sign in" }, SLOW)).toBeInTheDocument();
  });

  it("G5 every user except the admins must choose a new password at sign-in", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    for (const who of [ACCOUNTS.marc, ACCOUNTS.ines]) {
      submitSignIn(who.email, who.password);
      expect(await s.findByRole("heading", { name: "Choose a new password" }, SLOW)).toBeInTheDocument();
      expect(s.getByLabelText("New password")).toHaveAttribute("type", "password");
      expect(s.getByLabelText("Confirm new password")).toHaveAttribute("type", "password");
      expect(s.getByRole("button", { name: "Save password" })).toBeInTheDocument();
      expect(s.queryByRole("navigation", { name: "Primary" })).not.toBeInTheDocument();
      expect(s.queryByRole("heading", { level: 1, name: "Dashboard" })).not.toBeInTheDocument();
      closeApp();
      await openApp("/sign-in");
      await s.findByRole("heading", { name: "Sign in" }, SLOW);
    }
  });

  it("G5 admins go straight to the dashboard", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    submitSignIn(ACCOUNTS.dana.email, ACCOUNTS.dana.password);
    await onPage("Dashboard");
    expect(s.queryByRole("heading", { name: "Choose a new password" })).not.toBeInTheDocument();
    await signOut("Dana Whitaker");
    submitSignIn(ACCOUNTS.owen.email, ACCOUNTS.owen.password);
    await onPage("Dashboard");
    expect(s.queryByRole("heading", { name: "Choose a new password" })).not.toBeInTheDocument();
  });

  it("G6 nobody is locked out: many wrong attempts, then the right password works", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    for (let attempt = 0; attempt < 6; attempt += 1) {
      submitSignIn(ACCOUNTS.dana.email, `wrong-${attempt}`);
      expect(await s.findByRole("alert", {}, SLOW)).toHaveTextContent(MESSAGE);
      await waitFor(() => expect(s.getByRole("button", { name: "Sign in" })).toBeEnabled(), SLOW);
    }
    submitSignIn(ACCOUNTS.dana.email, ACCOUNTS.dana.password);
    await onPage("Dashboard");
  });

  it("G6 someone who still has to change their password signs in with the current one, with no error", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    for (let attempt = 0; attempt < 6; attempt += 1) {
      submitSignIn(ACCOUNTS.ines.email, `wrong-${attempt}`);
      await s.findByRole("alert", {}, SLOW);
      await waitFor(() => expect(s.getByRole("button", { name: "Sign in" })).toBeEnabled(), SLOW);
    }
    submitSignIn(ACCOUNTS.ines.email, ACCOUNTS.ines.password);
    expect(await s.findByRole("heading", { name: "Choose a new password" }, SLOW)).toBeInTheDocument();
    expect(s.queryByText(/expired|locked|too many/i)).not.toBeInTheDocument();
  });

  it("G7 one exact message for an unknown email, a wrong password and the demo password", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    const seen: string[] = [];
    for (const [email, password] of [
      ["nobody@pulse.test", ACCOUNTS.dana.password],
      [ACCOUNTS.marc.email, "not-the-password"],
      [ACCOUNTS.owen.email, "demo"],
    ] as const) {
      submitSignIn(email, password);
      const alert = await s.findByRole("alert", {}, SLOW);
      expect(s.getAllByRole("alert")).toHaveLength(1);
      seen.push(alert.textContent ?? "");
      await waitFor(() => expect(s.getByRole("button", { name: "Sign in" })).toBeEnabled(), SLOW);
    }
    expect(seen).toEqual([MESSAGE, MESSAGE, MESSAGE]);
    expect(seen[0]).toBe("Wrong email or password.");
  });

  it("G8 the new password must be at least 10 characters and must match", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    submitSignIn(ACCOUNTS.marc.email, ACCOUNTS.marc.password);
    await s.findByRole("heading", { name: "Choose a new password" }, SLOW);
    await fillNewPassword(s, "short", "short");
    expect(await s.findByText("Use at least 10 characters.")).toBeInTheDocument();
    await fillNewPassword(s, NEW_PASSWORD, `${NEW_PASSWORD}x`);
    expect(await s.findByText("Passwords do not match.")).toBeInTheDocument();
    expect(s.queryByText("Use at least 10 characters.")).not.toBeInTheDocument();
    expect(s.getByRole("heading", { name: "Choose a new password" })).toBeInTheDocument();
    expect(localStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("G8 saving signs the person in; the new password works from then on and the old one does not", async () => {
    const s = await openApp("/sign-in");
    await s.findByRole("heading", { name: "Sign in" }, SLOW);
    submitSignIn(ACCOUNTS.marc.email, ACCOUNTS.marc.password);
    await s.findByRole("heading", { name: "Choose a new password" }, SLOW);
    await fillNewPassword(s, NEW_PASSWORD, NEW_PASSWORD);
    await onPage("Dashboard");
    expect(s.getByRole("button", { name: "Marc Ellery" })).toBeInTheDocument();
    await signOut("Marc Ellery");
    submitSignIn(ACCOUNTS.marc.email, ACCOUNTS.marc.password);
    expect(await s.findByRole("alert", {}, SLOW)).toHaveTextContent(MESSAGE);
    await waitFor(() => expect(s.getByRole("button", { name: "Sign in" })).toBeEnabled(), SLOW);
    submitSignIn(ACCOUNTS.marc.email, NEW_PASSWORD);
    await onPage("Dashboard");
    expect(s.queryByRole("heading", { name: "Choose a new password" })).not.toBeInTheDocument();
  });
});
