let counter = 0;

/** A short id that is unique within this browser session, e.g. `note-lx2k9a-3`. */
export function createId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter}`;
}
