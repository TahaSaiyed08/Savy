"use client";
import { useRef, useState } from "react";
import { EmptyState, InsetGroup, LargeTitle, Status } from "@/components/ui";
import { Plus, ReceiptText } from "@/components/icons";
import { AddMethodsSheet, type AddMethod } from "@/components/list/AddMethodsSheet";
import { ReceiptLoading } from "@/components/list/ReceiptLoading";
import { ReceiptConfirmSheet } from "@/components/list/ReceiptConfirmSheet";
import { PickProductSheet } from "@/components/list/PickProductSheet";
import { TypeOrSaySheet } from "@/components/list/TypeOrSaySheet";
import { ListRow } from "@/components/list/ListRow";
import { api, withUser, type Schemas } from "@/lib/api";
import { useItems } from "@/lib/use-items";

type Flow =
  | { step: "closed" }
  | { step: "methods" }
  | { step: "receipt-loading"; previewUrl?: string }
  | { step: "receipt-confirm"; extraction: Schemas["Extraction"] }
  | { step: "pick-loading"; previewUrl?: string }
  | { step: "pick-product"; previewUrl?: string; candidates: Schemas["ExtractedItem"][] }
  | { step: "type" };

export default function MyList() {
  const { items, loading, error, addItems, deleteItem } = useItems();
  const [flow, setFlow] = useState<Flow>({ step: "closed" });
  const [saving, setSaving] = useState(false);
  const receiptInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);

  function pickMethod(method: AddMethod) {
    if (method === "receipt") receiptInput.current?.click();
    else if (method === "photo") photoInput.current?.click();
    else setFlow({ step: "type" });
  }

  async function onReceiptFile(file: File) {
    const previewUrl = URL.createObjectURL(file);
    setFlow({ step: "receipt-loading", previewUrl });
    const form = new FormData();
    form.set("file", file, file.name);
    try {
      const { data, error } = await api.POST("/intake/receipt", { params: withUser(), body: form as never });
      if (error || !data) throw new Error();
      setFlow({ step: "receipt-confirm", extraction: data.extraction });
    } catch {
      setFlow({ step: "closed" });
    }
  }

  async function onPhotoFile(file: File) {
    const previewUrl = URL.createObjectURL(file);
    setFlow({ step: "pick-loading", previewUrl });
    const form = new FormData();
    form.set("file", file, file.name);
    try {
      const { data, error } = await api.POST("/intake/photo", { params: withUser(), body: form as never });
      if (error || !data) throw new Error();
      setFlow({ step: "pick-product", previewUrl, candidates: data.extraction.items });
    } catch {
      setFlow({ step: "closed" });
    }
  }

  async function saveItems(extracted: Schemas["ExtractedItem"][], source: Schemas["SaveItems"]["source"]) {
    setSaving(true);
    await addItems({ items: extracted, source });
    setSaving(false);
    setFlow({ step: "closed" });
  }

  return (
    <>
      <LargeTitle
        title="My List"
        action={
          <button
            type="button"
            onClick={() => setFlow({ step: "methods" })}
            aria-label="Add item"
            className="flex size-11 items-center justify-center rounded-full border border-separator bg-bg text-tint"
          >
            <Plus size={27} />
          </button>
        }
      />

      <Status loading={loading} error={error} />

      {!loading && !error && items?.length === 0 && (
        <EmptyState
          icon={<ReceiptText size={52} />}
          title="Snap a receipt to fill your list."
          primaryLabel="Scan a receipt"
          onPrimary={() => receiptInput.current?.click()}
          secondaryLabel="Or add one item"
          onSecondary={() => setFlow({ step: "type" })}
        />
      )}

      {!!items?.length && (
        <InsetGroup header={`${items.length} item${items.length === 1 ? "" : "s"}`}>
          {items.map((i) => (
            <ListRow key={i.user_item_id} item={i} onDelete={() => deleteItem(i.user_item_id)} />
          ))}
        </InsetGroup>
      )}

      <input
        ref={receiptInput}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onReceiptFile(file);
        }}
      />
      <input
        ref={photoInput}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onPhotoFile(file);
        }}
      />

      <AddMethodsSheet open={flow.step === "methods"} onClose={() => setFlow({ step: "closed" })} onPick={pickMethod} />

      {(flow.step === "receipt-loading" || flow.step === "pick-loading") && (
        <ReceiptLoading previewUrl={flow.previewUrl} onCancel={() => setFlow({ step: "closed" })} />
      )}

      {flow.step === "receipt-confirm" && (
        <ReceiptConfirmSheet
          key="receipt-confirm"
          open
          extraction={flow.extraction}
          onClose={() => setFlow({ step: "closed" })}
          saving={saving}
          onSave={(chosen) => saveItems(chosen, "receipt")}
        />
      )}

      {flow.step === "pick-product" && (
        <PickProductSheet
          key="pick-product"
          open
          previewUrl={flow.previewUrl}
          candidates={flow.candidates}
          onClose={() => setFlow({ step: "closed" })}
          saving={saving}
          onAdd={(item) => saveItems([item], "photo")}
        />
      )}

      {flow.step === "type" && (
        <TypeOrSaySheet
          key="type"
          open
          onClose={() => setFlow({ step: "closed" })}
          saving={saving}
          onAdd={(item, source) => saveItems([item], source)}
        />
      )}
    </>
  );
}
