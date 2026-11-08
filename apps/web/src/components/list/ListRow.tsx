"use client";
import { Pencil, ShoppingCart, Trash } from "@/components/icons";
import { ItemContent } from "@/components/list/ItemContent";
import { SwipeRow } from "@/components/SwipeRow";
import { fullName } from "@/lib/format";
import type { Schemas } from "@/lib/api";

/** Pantry row: swipe right to move it to the Basket, left to edit or delete. Tap opens Price Match. */
export function ListRow({
  item,
  onTap,
  onToggleBasket,
  onEdit,
  onDelete,
  editMode,
}: {
  item: Schemas["ListItem"];
  onTap: () => void;
  onToggleBasket: () => void;
  onEdit: () => void;
  onDelete: () => void;
  editMode?: boolean;
}) {
  const name = fullName(item);
  const basketLabel = item.in_basket ? "Remove from Basket" : "Move to Basket";
  if (editMode) {
    return (
      <li className="flex min-h-tap items-center gap-1 pl-1 pr-2">
        <button type="button" onClick={onDelete} aria-label={`Delete: ${name}`} className="flex size-11 shrink-0 items-center justify-center text-destructive">
          <Trash size={20} />
        </button>
        <button type="button" onClick={onEdit} aria-label={`Edit: ${name}`} className="flex min-w-0 flex-1 items-center gap-3 py-2 text-left">
          <ItemContent item={item} />
        </button>
        <Pencil size={18} className="shrink-0 text-label-2" aria-hidden />
      </li>
    );
  }
  return (
    <SwipeRow
      onTap={onTap}
      leading={[{ key: "basket", label: item.in_basket ? "Remove" : "Basket", ariaLabel: `${basketLabel}: ${name}`, icon: <ShoppingCart size={20} />, cls: "bg-tint text-on-tint", onClick: onToggleBasket, full: true }]}
      trailing={[
        { key: "edit", label: "Edit", ariaLabel: `Edit: ${name}`, icon: <Pencil size={20} />, cls: "bg-info text-white", onClick: onEdit },
        { key: "delete", label: "Delete", ariaLabel: `Delete: ${name}`, icon: <Trash size={20} />, cls: "bg-destructive text-white", onClick: onDelete, full: true },
      ]}
    >
      <ItemContent item={item} inBasketMark />
    </SwipeRow>
  );
}
