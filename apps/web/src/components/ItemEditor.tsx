"use client";
// Shared editable brand/item/variant/size form: reused by the receipt edit-item sheet, the pick-product
// sheet, and the type-or-say parsed screen, so the three "confirm what we think you mean" flows match.
import { FieldRow, UnitPicker } from "@/components/ui";
import type { Schemas } from "@/lib/api";

export type ItemDraft = {
  brand: string;
  item: string;
  variant: string;
  size_qty: string;
  size_unit: string;
};

export function draftFrom(i: Partial<Schemas["ExtractedItem"]>): ItemDraft {
  return {
    brand: i.brand ?? "",
    item: i.item ?? "",
    variant: i.variant ?? "",
    size_qty: i.size_qty != null ? String(i.size_qty) : "",
    size_unit: i.size_unit ?? "",
  };
}

export function draftToItem(d: ItemDraft, confidence = 1): Schemas["ExtractedItem"] {
  const qty = parseFloat(d.size_qty);
  return {
    brand: d.brand.trim() || null,
    item: d.item.trim(),
    variant: d.variant.trim() || null,
    size_qty: Number.isFinite(qty) ? qty : null,
    size_unit: d.size_unit.trim() || null,
    confidence,
  };
}

export function ItemEditor({ draft, onChange }: { draft: ItemDraft; onChange: (d: ItemDraft) => void }) {
  return (
    <div className="overflow-hidden rounded-[16px] border border-separator bg-elevated shadow-[0_4px_16px_0_rgba(0,0,0,0.04)]">
      <FieldRow label="Brand" value={draft.brand} placeholder="Any brand" onChange={(v) => onChange({ ...draft, brand: v })} />
      <FieldRow label="Item" value={draft.item} onChange={(v) => onChange({ ...draft, item: v })} />
      <FieldRow label="Variant" value={draft.variant} placeholder="—" onChange={(v) => onChange({ ...draft, variant: v })} />
      <FieldRow
        label="Size"
        value={draft.size_qty}
        placeholder="—"
        onChange={(v) => onChange({ ...draft, size_qty: v.replace(/[^0-9.]/g, "") })}
      />
      <div className="p-3">
        <UnitPicker value={draft.size_unit} onChange={(u) => onChange({ ...draft, size_unit: u })} />
      </div>
    </div>
  );
}
