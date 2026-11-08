"use client";
import { Check, Trash } from "@/components/icons";
import { ItemContent } from "@/components/list/ItemContent";
import { SwipeRow } from "@/components/SwipeRow";
import { fullName } from "@/lib/format";
import type { Schemas } from "@/lib/api";

/** Basket row: swipe right for Done (or back again), left to delete, or tap the circle. Tap the row for Price Match. */
export function BasketRow({
  item,
  onTap,
  onToggleDone,
  onDelete,
}: {
  item: Schemas["ListItem"];
  onTap: () => void;
  onToggleDone: () => void;
  onDelete: () => void;
}) {
  const name = fullName(item);
  const action = item.done ? "Not done" : "Done";
  return (
    <SwipeRow
      sep={112}
      onTap={onTap}
      leading={[{ key: "done", label: action, ariaLabel: `${action}: ${name}`, icon: <Check size={20} />, cls: "bg-tint text-on-tint", onClick: onToggleDone, full: true }]}
      trailing={[{ key: "delete", label: "Delete", ariaLabel: `Delete: ${name}`, icon: <Trash size={20} />, cls: "bg-destructive text-white", onClick: onDelete, full: true }]}
    >
      <button
        type="button"
        aria-pressed={item.done}
        aria-label={`Mark done: ${name}`}
        onPointerDown={(e) => e.stopPropagation()}
        onPointerUp={(e) => e.stopPropagation()}
        onClick={onToggleDone}
        className="-my-2 -ml-1.5 flex size-11 shrink-0 items-center justify-center"
      >
        <span className={`flex size-[26px] items-center justify-center rounded-full border-2 ${item.done ? "border-tint bg-tint text-on-tint" : "border-label-2/50"}`}>
          {item.done && <Check size={16} />}
        </span>
      </button>
      <ItemContent item={item} struck={item.done} />
    </SwipeRow>
  );
}
