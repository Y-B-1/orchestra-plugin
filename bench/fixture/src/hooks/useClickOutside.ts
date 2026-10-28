import { useEffect, type RefObject } from "react";

/** Calls `onOutside` for pointer presses outside `ref` while `active` is true. */
export function useClickOutside(ref: RefObject<HTMLElement | null>, onOutside: () => void, active = true): void {
  useEffect(() => {
    if (!active) return undefined;
    function onPointerDown(event: MouseEvent) {
      const node = ref.current;
      if (node && event.target instanceof Node && !node.contains(event.target)) onOutside();
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [ref, onOutside, active]);
}
