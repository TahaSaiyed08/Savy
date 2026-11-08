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
}: {
  item: Schemas["ListItem"];
  onTap: () => void;
  onToggleBasket: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const name = fullName(item);
  const basketLabel = item.in_basket ? "Remove from Basket" : "Move to Basket";
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
