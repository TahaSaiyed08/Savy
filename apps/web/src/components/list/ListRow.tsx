"use client";
// Swipe-left row with up to 3 revealed actions (Basket / Edit / Delete), iOS Mail-style. Works with pointer
// events so it responds to touch, mouse (desktop review) and pen alike. A plain tap (not a swipe) calls
// onTap -- Pantry uses this to jump straight to the item's cheapest flyer match.
import { useRef, useState } from "react";
import { ShoppingCart } from "@/components/icons";
import type { Schemas } from "@/lib/api";

const ACTION_W = 76;
const DRAG_THRESHOLD = 6; // px of horizontal movement before a pointer-down counts as a swipe, not a tap

type Action = { key: string; label: string; cls: string; icon?: React.ReactNode; onClick: () => void };

export function ListRow({
  item,
  onTap,
  onToggleBasket,
  onEdit,
  onDelete,
}: {
  item: Schemas["UserItem"];
  /** Plain tap on the (unswiped) row. Pantry uses this to open the item's cheapest deal. */
  onTap?: () => void;
  /** Omit to hide the Basket action entirely (e.g. inside the Basket page itself). */
  onToggleBasket?: () => void;
  onEdit?: () => void;
  onDelete: () => void;
}) {
  const [dx, setDx] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const drag = useRef<{ startX: number; startDx: number; moved: boolean } | null>(null);

  const actions: Action[] = [
    ...(onToggleBasket
      ? [{
          key: "basket",
          label: item.in_basket ? "Remove from Basket" : "Move to Basket",
          cls: "bg-tint",
          icon: <ShoppingCart size={20} />,
          onClick: onToggleBasket,
        }]
      : []),
    ...(onEdit ? [{ key: "edit", label: "Edit", cls: "bg-separator text-label", onClick: onEdit }] : []),
    { key: "delete", label: "Delete", cls: "bg-destructive", onClick: onDelete },
  ];
  const OPEN = -ACTION_W * actions.length;

  function onPointerDown(e: React.PointerEvent) {
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startDx: dx, moved: false };
    setIsDragging(true);
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!drag.current) return;
    const delta = e.clientX - drag.current.startX;
    if (Math.abs(delta) > DRAG_THRESHOLD) drag.current.moved = true;
    setDx(Math.max(OPEN, Math.min(0, drag.current.startDx + delta)));
  }
  function endDrag() {
    const d = drag.current;
    drag.current = null;
    setIsDragging(false);
    if (d && !d.moved) {
      // A genuine tap: closes an open row, or (if already closed) triggers onTap.
      if (dx !== 0) setDx(0);
      else onTap?.();
      return;
    }
    setDx((cur) => (cur < OPEN / 2 ? OPEN : 0));
  }

  const title = [item.brand, item.item, item.variant].filter(Boolean).join(" ") || item.item;
  const subtitle = item.size_qty ? `${item.size_qty} ${item.size_unit}` : undefined;

  return (
    <li className="relative overflow-hidden [&:not(:last-child)]:border-b [&:not(:last-child)]:border-separator">
      <div className="absolute inset-y-0 right-0 flex">
        {actions.map((a) => (
          <button
            key={a.key}
            type="button"
            onClick={() => {
              setDx(0);
              a.onClick();
            }}
            onFocus={() => setDx(OPEN)}
            onBlur={() => setDx(0)}
            aria-label={`${a.label}: ${title}`}
            style={{ width: ACTION_W }}
            className={`flex flex-col items-center justify-center gap-0.5 text-[13px] text-white focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-white ${a.cls}`}
          >
            {a.icon}
            {a.label.split(" ")[0]}
          </button>
        ))}
      </div>
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
        {item.in_basket && <ShoppingCart size={16} className="shrink-0 text-tint" />}
        <p className="shrink-0 text-[13px] text-label-2">{item.source}</p>
      </div>
    </li>
  );
}
