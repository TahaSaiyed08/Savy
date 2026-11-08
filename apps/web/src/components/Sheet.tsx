"use client";
import { useEffect, type ReactNode } from "react";

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
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        className={`absolute inset-x-0 bottom-0 mx-auto flex w-full max-w-xl flex-col overflow-hidden rounded-t-[24px] bg-bg shadow-sheet ${
          tall ? "top-[6vh] max-h-[94vh]" : "max-h-[85vh]"
        }`}
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
