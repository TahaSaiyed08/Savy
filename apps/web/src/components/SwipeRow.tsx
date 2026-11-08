"use client";
// A list row with actions behind it on either side, iOS Mail-style. Pointer events, so touch, mouse and pen all work.
// A tap (no drag) calls onTap. Dragging past 60% of the row commits that side's `full` action.
import { useRef, useState, type CSSProperties, type ReactNode } from "react";

const ACTION_W = 76;
const DRAG_THRESHOLD = 6;
const FULL_SWIPE = 0.6;

export type SwipeAction = { key: string; label: string; ariaLabel: string; icon?: ReactNode; cls: string; onClick: () => void; full?: boolean };

export function SwipeRow({
  leading = [],
  trailing = [],
  onTap,
  sep = 70,
  children,
}: {
  leading?: SwipeAction[];
  trailing?: SwipeAction[];
  onTap?: () => void;
  sep?: number;
  children: ReactNode;
}) {
  const [dx, setDx] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ startX: number; startDx: number; moved: boolean } | null>(null);

  const openLeft = ACTION_W * leading.length;
  const openRight = -ACTION_W * trailing.length;
  const fullOf = (side: SwipeAction[]) => side.find((a) => a.full);

  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startDx: dx, moved: false };
    setIsDragging(true);
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!drag.current) return;
    const delta = e.clientX - drag.current.startX;
    if (Math.abs(delta) > DRAG_THRESHOLD) drag.current.moved = true;
    const width = rowRef.current?.offsetWidth ?? 0;
    const max = fullOf(leading) ? width : openLeft;
    const min = fullOf(trailing) ? -width : openRight;
    setDx(Math.max(min, Math.min(max, drag.current.startDx + delta)));
  }
  function endDrag() {
    const d = drag.current;
    drag.current = null;
    setIsDragging(false);
    if (d && !d.moved) {
      if (dx !== 0) setDx(0);
      else onTap?.();
      return;
    }
    const width = rowRef.current?.offsetWidth ?? Infinity;
    const full = dx > 0 ? fullOf(leading) : fullOf(trailing);
    if (full && Math.abs(dx) >= width * FULL_SWIPE) {
      setDx(0);
      full.onClick();
      return;
    }
    setDx(dx > openLeft / 2 && openLeft ? openLeft : dx < openRight / 2 && openRight ? openRight : 0);
  }

  const button = (a: SwipeAction, open: number) => (
    <button
      key={a.key}
      type="button"
      onClick={() => {
        setDx(0);
        a.onClick();
      }}
      onFocus={() => setDx(open)}
      onBlur={() => setDx(0)}
      aria-label={a.ariaLabel}
      className={`flex min-w-[76px] flex-1 flex-col items-center justify-center gap-0.5 text-[13px] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-white ${a.cls}`}
    >
      {a.icon}
      {a.label}
    </button>
  );

  return (
    <li className="relative overflow-hidden">
      {/* Transparent until revealed, not hidden: the buttons stay reachable to keyboards and VoiceOver. */}
      <div className={`absolute inset-y-0 left-0 flex ${dx > 0 ? "" : "opacity-0"}`} style={{ width: Math.max(openLeft, dx) }}>
        {leading.map((a) => button(a, openLeft))}
      </div>
      <div className={`absolute inset-y-0 right-0 flex ${dx < 0 ? "" : "opacity-0"}`} style={{ width: Math.max(-openRight, -dx) }}>
        {trailing.map((a) => button(a, openRight))}
      </div>
      <div
        ref={rowRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        style={{ transform: `translateX(${dx}px)`, transition: isDragging ? "none" : "transform 180ms", "--sep": `${sep}px` } as CSSProperties}
        className="row-sep relative z-10 flex min-h-[3.75rem] cursor-pointer touch-pan-y select-none items-center gap-3 bg-elevated px-3.5 py-3"
      >
        {children}
      </div>
    </li>
  );
}
