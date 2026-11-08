"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** HIG bottom sheet: grabber, nav bar (Cancel / title / optional action), backdrop dismiss, Esc to close. */
export function Sheet({
  open,
  onClose,
  title,
  cancelLabel = "Cancel",
  onCancel,
  action,
  tall = false,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  cancelLabel?: string;
  onCancel?: () => void;
  /** Right-side nav action, e.g. a disabled "Save" label — pass a full element so callers control state. */
  action?: ReactNode;
  /** Tall sheets (confirm items, pick product) sit near the top instead of hugging their content. */
  tall?: boolean;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusTo = useRef<HTMLElement | null>(null);
  // Starts off-screen/transparent and flips true a frame after mount, so the slide-up + fade-in actually
  // transitions instead of snapping straight to its open state.
  const [entered, setEntered] = useState(false);
  // Several callers pass a fresh `onClose` arrow function on every render (e.g. TypeOrSaySheet re-renders
  // on every keystroke); depending on it directly would re-run this effect — and re-steal focus to Cancel
  // — on every keystroke. A ref keeps the handler current without that.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const focusables = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      // Keep Tab cycling inside the sheet, so keyboard focus can't land on content behind it.
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    restoreFocusTo.current = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    const raf = requestAnimationFrame(() => setEntered(true));

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      restoreFocusTo.current?.focus();
      cancelAnimationFrame(raf);
      setEntered(false);
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={title}>
      <div
        className={`absolute inset-0 bg-black/40 transition-opacity motion-reduce:transition-none ${entered ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        className={`absolute inset-x-0 bottom-0 mx-auto flex w-full max-w-xl flex-col overflow-hidden rounded-t-[24px] bg-bg shadow-sheet transition-transform ease-out motion-reduce:transition-none ${
          entered ? "translate-y-0" : "translate-y-full"
        } ${tall ? "top-[6vh] max-h-[94vh]" : "max-h-[85vh]"}`}
      >
        <div className="flex h-5 shrink-0 items-center justify-center">
          <div className="h-[5px] w-9 rounded-full bg-label-2/40" />
        </div>
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-separator/60 px-4">
          <button
            type="button"
            onClick={onCancel ?? onClose}
            className="flex h-tap min-w-[72px] items-center text-[17px] font-semibold text-tint"
          >
            {cancelLabel}
          </button>
          <p className="flex-1 text-center text-[17px] font-semibold">{title}</p>
          <div className="flex h-tap min-w-[72px] items-center justify-end">{action}</div>
        </div>
        <div className="flex-1 overflow-y-auto overscroll-contain" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
          {children}
        </div>
      </div>
    </div>
  );
}
