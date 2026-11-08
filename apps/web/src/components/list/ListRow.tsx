"use client";
// Swipe-left-to-delete row, matching the Figma "Delete action" reveal. Works with pointer events so it
// responds to touch, mouse (desktop review) and pen alike.
import { useRef, useState } from "react";
import type { Schemas } from "@/lib/api";

const OPEN = -76;

export function ListRow({ item, onDelete }: { item: Schemas["UserItem"]; onDelete: () => void }) {
  const [dx, setDx] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const drag = useRef<{ startX: number; startDx: number } | null>(null);

  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startDx: dx };
    setIsDragging(true);
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!drag.current) return;
    const delta = e.clientX - drag.current.startX;
    setDx(Math.max(OPEN, Math.min(0, drag.current.startDx + delta)));
  }
  function endDrag() {
    if (!drag.current) return;
    drag.current = null;
    setIsDragging(false);
    setDx((d) => (d < OPEN / 2 ? OPEN : 0));
  }

  const title = [item.brand, item.item, item.variant].filter(Boolean).join(" ") || item.item;
  const subtitle = item.size_qty ? `${item.size_qty} ${item.size_unit}` : undefined;

  return (
    <li className="relative overflow-hidden [&:not(:last-child)]:border-b [&:not(:last-child)]:border-separator">
      <button
        type="button"
        onClick={() => {
          setDx(0);
          onDelete();
        }}
        aria-label={`Delete ${title}`}
        className="absolute inset-y-0 right-0 flex w-[76px] items-center justify-center bg-destructive text-[17px] text-white"
      >
        Delete
      </button>
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        style={{ transform: `translateX(${dx}px)`, transition: isDragging ? "none" : "transform 180ms" }}
        className="relative z-10 flex min-h-[4.625rem] touch-pan-y items-center gap-2 bg-elevated px-4 py-3"
      >
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px]">{title}</p>
          {subtitle && <p className="truncate text-[15px] text-label-2">{subtitle}</p>}
        </div>
        <p className="shrink-0 text-[13px] text-label-2">{item.source}</p>
      </div>
    </li>
  );
}
