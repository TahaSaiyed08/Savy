"use client";
// Confirm-items sheet: low-confidence lines ("CHECK THESE") always need a look and route to the edit
// form; everything else ("LOOKS RIGHT") is pre-selected with a tap-to-exclude checkmark, per the design.
import { useState } from "react";
import { Sheet } from "@/components/Sheet";
import { PrimaryButton } from "@/components/ui";
import { CircleCheck, TriangleAlert } from "@/components/icons";
import { ItemEditor, draftFrom, draftToItem, type ItemDraft } from "@/components/ItemEditor";
import type { Schemas } from "@/lib/api";

const CONFIRM_BELOW = 0.6;

function label(it: Schemas["ExtractedItem"]) {
  const size = it.size_qty && it.size_unit ? ` · ${it.size_qty} ${it.size_unit}` : "";
  return `${[it.brand, it.item, it.variant].filter(Boolean).join(" ")}${size}`;
}

export function ReceiptConfirmSheet({
  open,
  extraction,
  onClose,
  onSave,
  saving,
}: {
  open: boolean;
  extraction: Schemas["Extraction"];
  onClose: () => void;
  onSave: (items: Schemas["ExtractedItem"][]) => void;
  saving?: boolean;
}) {
  const [items, setItems] = useState(extraction.items);
  const [selected, setSelected] = useState<Set<number>>(() => new Set(extraction.items.map((_, i) => i)));
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<ItemDraft | null>(null);

  function startEdit(i: number) {
    setEditingIndex(i);
    setDraft(draftFrom(items[i]));
  }
  function finishEdit() {
    if (editingIndex == null || !draft) return;
    setItems((prev) => prev.map((it, i) => (i === editingIndex ? draftToItem(draft, 1) : it)));
    setEditingIndex(null);
    setDraft(null);
  }
  function toggle(i: number) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  if (editingIndex != null && draft) {
    return (
      <Sheet
        open={open}
        onClose={() => {
          setEditingIndex(null);
          setDraft(null);
        }}
        title="Edit item"
        action={
          <button type="button" onClick={finishEdit} className="text-[17px] font-semibold text-tint">
            Done
          </button>
        }
      >
        <div className="p-4">
          <ItemEditor draft={draft} onChange={setDraft} />
        </div>
      </Sheet>
    );
  }

  const low = items.map((it, i) => ({ it, i })).filter(({ it }) => it.confidence < CONFIRM_BELOW);
  const ok = items.map((it, i) => ({ it, i })).filter(({ it }) => it.confidence >= CONFIRM_BELOW);
  const chosenItems = items.filter((it, i) => it.confidence < CONFIRM_BELOW || selected.has(i));
  const date = extraction.bought_at
    ? new Date(extraction.bought_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : undefined;
  const headerLine = [extraction.store, date, `${items.length} items`].filter(Boolean).join(" · ");

  return (
    <Sheet open={open} onClose={onClose} title="Confirm items" tall action={<span className="w-[72px]" />}>
      <div className="flex flex-col gap-1 px-4 pt-3 pb-24">
        <p className="text-[15px] font-medium text-label-2">{headerLine}</p>

        {low.length > 0 && (
          <>
            <div className="flex items-center gap-1.5 pt-5 pb-2">
              <TriangleAlert size={16} className="text-warning-text" />
              <p className="text-[13px] font-semibold text-warning-text">CHECK THESE</p>
            </div>
            <div className="overflow-hidden rounded-[16px] border border-warning-border bg-warning-bg shadow-[0_4px_12px_0_rgba(0,0,0,0.03)]">
              {low.map(({ it, i }) => (
                <div key={i} className="flex items-center gap-2 border-b border-warning-border px-3.5 py-3 last:border-b-0">
                  <p className="min-w-0 flex-1 truncate text-[17px] font-semibold text-label">{label(it)}</p>
                  <button type="button" onClick={() => startEdit(i)} className="flex h-tap items-center text-[17px] text-tint">
                    Edit
                  </button>
                </div>
              ))}
            </div>
          </>
        )}

        {ok.length > 0 && (
          <>
            <div className="pt-5 pb-2">
              <p className="text-[13px] font-semibold text-label-2">LOOKS RIGHT</p>
            </div>
            <div className="overflow-hidden rounded-[16px] border border-separator bg-elevated shadow-[0_4px_12px_0_rgba(0,0,0,0.03)]">
              {ok.map(({ it, i }) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => toggle(i)}
                  className="flex h-12 w-full items-center gap-3 border-b border-separator px-3.5 last:border-b-0"
                >
                  <CircleCheck size={22} className={selected.has(i) ? "text-tint" : "text-label-2/40"} />
                  <p className="min-w-0 flex-1 truncate text-left text-[17px]">{label(it)}</p>
                </button>
              ))}
            </div>
            <p className="pt-2 pl-4 text-[13px] text-label-2">Tap a checkmark to leave an item out.</p>
          </>
        )}

        <div className="pt-6">
          <PrimaryButton onClick={() => onSave(chosenItems)} disabled={chosenItems.length === 0} loading={saving}>
            Save {chosenItems.length} item{chosenItems.length === 1 ? "" : "s"}
          </PrimaryButton>
        </div>
      </div>
    </Sheet>
  );
}
