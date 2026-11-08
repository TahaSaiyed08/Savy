"use client";
// "Which one is it?" — product-photo intake returns a top candidate plus alternates; user confirms or
// edits. The 108x108 preview is the photo they actually took, not a stock image.
import { useState } from "react";
import { Sheet } from "@/components/Sheet";
import { InlineError, PrimaryButton } from "@/components/ui";
import { Check } from "@/components/icons";
import { ItemEditor, draftFrom, draftToItem, type ItemDraft } from "@/components/ItemEditor";
import type { Schemas } from "@/lib/api";

function label(it: Schemas["ExtractedItem"]) {
  const size = it.size_qty && it.size_unit ? ` ${it.size_qty} ${it.size_unit}` : "";
  return `${[it.brand, it.item, it.variant].filter(Boolean).join(" ")}${size}`;
}

export function PickProductSheet({
  open,
  previewUrl,
  candidates,
  onClose,
  onAdd,
  saving,
  saveError,
  onRetrySave,
}: {
  open: boolean;
  previewUrl?: string;
  candidates: Schemas["ExtractedItem"][];
  onClose: () => void;
  onAdd: (item: Schemas["ExtractedItem"]) => void;
  saving?: boolean;
  /** Set when the last onAdd's /items call failed; "tap to retry" re-submits the same picked item. */
  saveError?: string;
  onRetrySave?: () => void;
}) {
  const [pickedIndex, setPickedIndex] = useState(0);
  const [draft, setDraft] = useState<ItemDraft>(() => draftFrom(candidates[0] ?? { item: "", confidence: 1 }));

  function pick(i: number) {
    setPickedIndex(i);
    setDraft(draftFrom(candidates[i]));
  }

  function submit() {
    onAdd(draftToItem(draft, candidates[pickedIndex]?.confidence ?? 1));
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Which one is it?"
      tall
      action={
        <button type="button" onClick={submit} disabled={!draft.item || saving} className="text-[17px] font-semibold text-tint disabled:opacity-40">
          Add
        </button>
      }
    >
      <div className="flex flex-col gap-5 px-4 pt-4 pb-6">
        <div className="flex justify-center">
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- transient blob: URL, not a static asset
            <img
              src={previewUrl}
              alt=""
              className="size-[108px] rounded-2xl border border-separator object-cover shadow-soft"
            />
          ) : (
            <div className="size-[108px] rounded-2xl bg-elevated" />
          )}
        </div>

        {candidates.length > 0 && (
          <div className="flex flex-col gap-3">
            {candidates.map((c, i) => (
              <button
                key={i}
                type="button"
                onClick={() => pick(i)}
                className={`flex min-h-tap items-center gap-2 rounded-full px-3 py-2.5 text-left text-[15px] ${
                  i === pickedIndex
                    ? "border-[1.5px] border-tint bg-savings-bg font-semibold text-tint shadow-tint"
                    : "border border-separator bg-elevated"
                }`}
              >
                <span className="min-w-0 flex-1 truncate">{label(c)}</span>
                {i === pickedIndex && <Check size={18} />}
              </button>
            ))}
          </div>
        )}

        <ItemEditor draft={draft} onChange={setDraft} />

        {saveError && onRetrySave && <InlineError message={saveError} onRetry={onRetrySave} />}
        <PrimaryButton onClick={submit} disabled={!draft.item} loading={saving}>
          Add to list
        </PrimaryButton>
      </div>
    </Sheet>
  );
}
