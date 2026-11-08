"use client";
import { useCallback, useRef, useState } from "react";

const UNDO_MS = 4000;

/** Returns show() and the node to render: a bottom toast with an optional Undo, gone after 4 s. */
export function useToast() {
  const [toast, setToast] = useState<{ message: string; undo?: () => void } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((message: string, undo?: () => void) => {
    if (timer.current) clearTimeout(timer.current);
    setToast({ message, undo });
    timer.current = setTimeout(() => setToast(null), UNDO_MS);
  }, []);

  const node = toast && (
    <div role="status" className="fixed inset-x-4 z-30 mx-auto flex max-w-md items-center justify-between gap-3 rounded-[14px] bg-toast px-4 py-3 text-[15px]" style={{ bottom: "calc(env(safe-area-inset-bottom) + 4.5rem)" }}>
      <span className="min-w-0 truncate">{toast.message}</span>
      {toast.undo && (
        <button
          type="button"
          onClick={() => {
            toast.undo?.();
            setToast(null);
          }}
          className="-my-2 min-h-tap shrink-0 font-semibold text-tint"
        >
          Undo
        </button>
      )}
    </div>
  );
  return { show, node };
}
