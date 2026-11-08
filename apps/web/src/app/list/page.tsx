"use client";
import { useRef, useState } from "react";
import { EmptyState, InsetGroup, LargeTitle, RetryButton, Skeleton, Status } from "@/components/ui";
import { Plus, ReceiptText } from "@/components/icons";
import { AddMethodsSheet, type AddMethod } from "@/components/list/AddMethodsSheet";
import { IntakeError, ReceiptLoading } from "@/components/list/ReceiptLoading";
import { ReceiptConfirmSheet } from "@/components/list/ReceiptConfirmSheet";
import { PickProductSheet } from "@/components/list/PickProductSheet";
import { TypeOrSaySheet } from "@/components/list/TypeOrSaySheet";
import { EditItemSheet } from "@/components/list/EditItemSheet";
import { ListRow } from "@/components/list/ListRow";
import { DealDetailSheet } from "@/components/deals/DealDetailSheet";
import { api, withUser, type Schemas } from "@/lib/api";
import { downscaleImage } from "@/lib/downscale";
import { intakeController, intakeErrorMessage } from "@/lib/intake";
import { useApi } from "@/lib/use-api";
import { useItems } from "@/lib/use-items";

type Flow =
  | { step: "closed" }
  | { step: "methods" }
  | { step: "receipt-loading"; previewUrl?: string }
  | { step: "receipt-confirm"; extraction: Schemas["Extraction"] }
  | { step: "pick-loading"; previewUrl?: string }
  | { step: "pick-product"; previewUrl?: string; candidates: Schemas["ExtractedItem"][] }
  | { step: "type" }
  | { step: "intake-error"; message: string };

type PendingSave = {
  items: Schemas["ExtractedItem"][];
  source: Schemas["SaveItems"]["source"];
  boughtAt?: string | null;
};

<<<<<<< HEAD
function ListSkeleton() {
  return (
    <section className="mx-4 mb-6">
      <Skeleton className="mb-1.5 ml-4 h-3 w-20" />
      <ul className="overflow-hidden rounded-[20px] bg-elevated shadow-card">
        {[0, 1, 2, 3].map((i) => (
          <li key={i} className="flex min-h-[4.625rem] items-center gap-2 border-b border-separator px-4 py-3 last:border-b-0">
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <Skeleton className="h-[17px] w-2/3" />
              <Skeleton className="h-[15px] w-1/3" />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function MyList() {
  const { items, loading, error, deleteError, addItems, deleteItem, refetch } = useItems();
=======
export default function Pantry() {
  const { items, loading, error, deleteError, addItems, deleteItem, setBasket, updateItem, refetch } = useItems();
  // Loaded once so tapping a Pantry row can jump straight to that item's cheapest flyer match, without a
  // network round trip per tap.
  const { data: deals } = useApi(() => api.GET("/deals", { params: withUser() }));
>>>>>>> origin/main
  const [flow, setFlow] = useState<Flow>({ step: "closed" });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | undefined>();
  const [activeDeal, setActiveDeal] = useState<Schemas["Deal"] | null>(null);
  const [editingItem, setEditingItem] = useState<Schemas["UserItem"] | null>(null);
  const receiptInput = useRef<HTMLInputElement>(null);
  const photoInput = useRef<HTMLInputElement>(null);
  const previewUrlRef = useRef<string | undefined>(undefined);
  const controllerRef = useRef<ReturnType<typeof intakeController> | null>(null);
  const pendingSaveRef = useRef<PendingSave | null>(null);

  function openCheapestDeal(item: Schemas["UserItem"]) {
    const matches = (deals ?? [])
      .filter((d) => d.user_item_id === item.user_item_id)
      .sort((a, b) => (a.unit_price ?? a.price ?? Infinity) - (b.unit_price ?? b.price ?? Infinity));
    if (matches[0]) setActiveDeal(matches[0]);
  }
  const otherStoresForActiveDeal = activeDeal
    ? (deals ?? []).filter((d) => d.item_label === activeDeal.item_label && d.flyer_item_id !== activeDeal.flyer_item_id)
    : [];

  function releasePreview() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = undefined;
    }
  }

  function closeFlow() {
    controllerRef.current?.cancel();
    releasePreview();
    setSaveError(undefined);
    pendingSaveRef.current = null;
    setFlow({ step: "closed" });
  }

  function pickMethod(method: AddMethod) {
    if (method === "receipt") receiptInput.current?.click();
    else if (method === "photo") photoInput.current?.click();
    else setFlow({ step: "type" });
  }

  async function onReceiptFile(file: File) {
    releasePreview();
    const small = await downscaleImage(file);
    const previewUrl = URL.createObjectURL(small);
    previewUrlRef.current = previewUrl;
    setFlow({ step: "receipt-loading", previewUrl });
    const ctl = intakeController();
    controllerRef.current = ctl;
    const form = new FormData();
    form.set("file", small, small.name);
    try {
      const { data, error, response } = await api.POST("/intake/receipt", {
        params: withUser(),
        body: form as never,
        signal: ctl.signal,
      });
      ctl.done();
      if (error || !data) {
        releasePreview();
        setFlow({ step: "intake-error", message: intakeErrorMessage(response) });
        return;
      }
      releasePreview(); // not needed by the confirm screen
      setFlow({ step: "receipt-confirm", extraction: data.extraction });
    } catch {
      ctl.done();
      if (ctl.wasCancelled()) return;
      releasePreview();
      setFlow({ step: "intake-error", message: intakeErrorMessage() });
    }
  }

  async function onPhotoFile(file: File) {
    releasePreview();
    const small = await downscaleImage(file);
    const previewUrl = URL.createObjectURL(small);
    previewUrlRef.current = previewUrl;
    setFlow({ step: "pick-loading", previewUrl });
    const ctl = intakeController();
    controllerRef.current = ctl;
    const form = new FormData();
    form.set("file", small, small.name);
    try {
      const { data, error, response } = await api.POST("/intake/photo", {
        params: withUser(),
        body: form as never,
        signal: ctl.signal,
      });
      ctl.done();
      if (error || !data) {
        releasePreview();
        setFlow({ step: "intake-error", message: intakeErrorMessage(response) });
        return;
      }
      setFlow({ step: "pick-product", previewUrl, candidates: data.extraction.items });
    } catch {
      ctl.done();
      if (ctl.wasCancelled()) return;
      releasePreview();
      setFlow({ step: "intake-error", message: intakeErrorMessage() });
    }
  }

  async function saveItems(
    extracted: Schemas["ExtractedItem"][],
    source: Schemas["SaveItems"]["source"],
    boughtAt?: string | null,
  ) {
    pendingSaveRef.current = { items: extracted, source, boughtAt };
    setSaveError(undefined);
    setSaving(true);
    try {
      await addItems({ items: extracted, source, bought_at: boughtAt ?? undefined });
      pendingSaveRef.current = null;
      releasePreview();
      setFlow({ step: "closed" });
    } catch {
      setSaveError("Couldn't save — tap to retry");
    } finally {
      setSaving(false);
    }
  }

  function retrySave() {
    const pending = pendingSaveRef.current;
    if (pending) saveItems(pending.items, pending.source, pending.boughtAt);
  }

  return (
    <>
      <LargeTitle
        title="Pantry"
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

      {loading && (
        <>
          <p role="status" className="sr-only">
            Loading…
          </p>
          <ListSkeleton />
        </>
      )}
      <Status error={error} />
      {error && <RetryButton onRetry={refetch} />}
      {deleteError && <p className="px-8 pb-4 text-center text-[13px] text-destructive">{deleteError}</p>}

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
            <ListRow
              key={i.user_item_id}
              item={i}
              onTap={() => openCheapestDeal(i)}
              onToggleBasket={() => setBasket(i.user_item_id, !i.in_basket)}
              onEdit={() => setEditingItem(i)}
              onDelete={() => deleteItem(i.user_item_id)}
            />
          ))}
        </InsetGroup>
      )}

      <input
        ref={receiptInput}
        data-testid="receipt-file-input"
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
        data-testid="photo-file-input"
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

      <AddMethodsSheet open={flow.step === "methods"} onClose={closeFlow} onPick={pickMethod} />

      {(flow.step === "receipt-loading" || flow.step === "pick-loading") && (
        <ReceiptLoading previewUrl={flow.previewUrl} onCancel={closeFlow} />
      )}

      {flow.step === "intake-error" && (
        <IntakeError message={flow.message} onRetry={() => setFlow({ step: "methods" })} onCancel={closeFlow} />
      )}

      {flow.step === "receipt-confirm" && (
        <ReceiptConfirmSheet
          key="receipt-confirm"
          open
          extraction={flow.extraction}
          onClose={closeFlow}
          saving={saving}
          saveError={saveError}
          onRetrySave={retrySave}
          onSave={(chosen) => saveItems(chosen, "receipt", flow.extraction.bought_at)}
        />
      )}

      {flow.step === "pick-product" && (
        <PickProductSheet
          key="pick-product"
          open
          previewUrl={flow.previewUrl}
          candidates={flow.candidates}
          onClose={closeFlow}
          saving={saving}
          saveError={saveError}
          onRetrySave={retrySave}
          onAdd={(item) => saveItems([item], "photo")}
        />
      )}

      {flow.step === "type" && (
        <TypeOrSaySheet
          key="type"
          open
          onClose={closeFlow}
          saving={saving}
          saveError={saveError}
          onRetrySave={retrySave}
          onAdd={(item, source) => saveItems([item], source)}
        />
      )}

      <DealDetailSheet deal={activeDeal} others={otherStoresForActiveDeal} onClose={() => setActiveDeal(null)} />

      <EditItemSheet
        item={editingItem}
        onClose={() => setEditingItem(null)}
        onSave={(fields) => updateItem(editingItem!.user_item_id, fields).then(() => {})}
      />
    </>
  );
}
