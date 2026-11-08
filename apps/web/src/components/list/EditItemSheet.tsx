"use client";
// Edits an existing Pantry item's identity (brand/item/variant/size) via PATCH /items/{id}.
import { useState } from "react";
import { Sheet } from "@/components/Sheet";
import { InlineError, PrimaryButton } from "@/components/ui";
import { ItemEditor, draftFrom, draftToItem, type ItemDraft } from "@/components/ItemEditor";
import type { Schemas } from "@/lib/api";

export function EditItemSheet({
  item,
  onClose,
  onSave,
}: {
  item: Schemas["UserItem"] | null;
  onClose: () => void;
  onSave: (item: Schemas["ExtractedItem"]) => Promise<void>;
}) {
  const [draft, setDraft] = useState<ItemDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const current = item ? (draft ?? draftFrom(item)) : null;
  if (item && !draft) setDraft(draftFrom(item));

  async function save() {
    if (!current) return;
    setSaving(true);
    setError(undefined);
    try {
      await onSave(draftToItem(current, 1));
      setDraft(null);
      onClose();
    } catch {
      setError("Couldn't save — tap to retry");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      open={!!item}
      onClose={() => {
        setDraft(null);
        onClose();
      }}
      title="Edit item"
      action={
        <button type="button" onClick={save} disabled={!current?.item || saving} className="text-[17px] font-semibold text-tint disabled:opacity-40">
          Save
        </button>
      }
    >
      {current && (
        <div className="flex flex-col gap-4 p-4">
          <ItemEditor draft={current} onChange={setDraft} />
          {error && <InlineError message={error} onRetry={save} />}
          <PrimaryButton onClick={save} disabled={!current.item} loading={saving}>
            Save changes
          </PrimaryButton>
        </div>
      )}
    </Sheet>
  );
}
