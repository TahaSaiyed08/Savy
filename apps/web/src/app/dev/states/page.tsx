"use client";
// Developer-only state gallery — not linked from the app's tab bar. Reaches every one of the 18 designed
// states for review. Most states are the REAL app driven with real (mock-mode) data: My List/Deals/Basket
// populated, the add-methods sheet, the full receipt and photo intake flows (any picked file works —
// MockExtractor returns a fixed extraction regardless of image content), and typed "type or say it" (hits
// the real /intake/manual). Two states are device-gated and get a static preview instead: "recording"
// needs mic permission, and the three "empty" screens need an empty list — the buttons below actually
// clear/restore the list via the real DELETE /items and POST /items endpoints so those are real too.
import Link from "next/link";
import { notFound } from "next/navigation";
import { useEffect, useState } from "react";
import { EmptyState, LargeTitle } from "@/components/ui";
import { ReceiptText, ShoppingCart, Tag } from "@/components/icons";
import { AddMethodsSheet } from "@/components/list/AddMethodsSheet";
import { ReceiptLoading } from "@/components/list/ReceiptLoading";
import { ReceiptConfirmSheet } from "@/components/list/ReceiptConfirmSheet";
import { PickProductSheet } from "@/components/list/PickProductSheet";
import { TypeOrSaySheet } from "@/components/list/TypeOrSaySheet";
import { DealDetailSheet } from "@/components/deals/DealDetailSheet";
import { getForcedTheme, setForcedTheme } from "@/components/ForceTheme";
import { api, withUser, type Schemas } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { useItems } from "@/lib/use-items";

// Mirrors apps/api/extractors.py MockExtractor exactly, so these previews match what the real endpoints
// return in mock mode (the default with no API keys set).
const MOCK_RECEIPT: Schemas["Extraction"] = {
  store: "Save-On-Foods",
  bought_at: "2026-11-06",
  items: [
    { brand: "PC", item: "chicken thigh", variant: "boneless", size_qty: 1, size_unit: "kg", price: 11.99, confidence: 0.93 },
    { item: "banana", size_qty: 1, size_unit: "lb", price: 0.79, confidence: 0.97 },
    { item: "eggs", variant: "large", size_qty: 12, size_unit: "ea", price: 4.49, confidence: 0.88 },
    { item: "oat milk", variant: "original", size_qty: 1.75, size_unit: "l", price: 5.29, confidence: 0.55 },
  ],
};
const MOCK_PRODUCT: Schemas["ExtractedItem"][] = [
  { brand: "Bertolli", item: "olive oil", variant: "extra virgin", size_qty: 1, size_unit: "l", confidence: 0.82 },
  { brand: "Bertolli", item: "olive oil", variant: "extra virgin", size_qty: 0.5, size_unit: "l", confidence: 0.4 },
];
const DEMO_SEED: Schemas["ExtractedItem"][] = [
  { item: "milk", variant: "2%", size_qty: 4, size_unit: "l", confidence: 1 },
  { item: "eggs", variant: "large", size_qty: 12, size_unit: "ea", confidence: 1 },
  { item: "banana", size_qty: 2, size_unit: "lb", confidence: 1 },
  { brand: "PC", item: "chicken thigh", variant: "boneless", size_qty: 1, size_unit: "kg", confidence: 1 },
  { item: "ramen", confidence: 1 },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mx-4 mb-6">
      <h2 className="px-1 pb-2 text-[13px] font-semibold tracking-wide text-label-2 uppercase">{title}</h2>
      <div className="flex flex-col gap-2 overflow-hidden rounded-[16px] border border-separator bg-elevated p-2">{children}</div>
    </section>
  );
}

function DevButton({ label, note, onClick, href }: { label: string; note?: string; onClick?: () => void; href?: string }) {
  const body = (
    <>
      <p className="text-[15px] font-medium">{label}</p>
      {note && <p className="text-[13px] text-label-2">{note}</p>}
    </>
  );
  const cls = "flex flex-col gap-0.5 rounded-xl px-3 py-2.5 text-left hover:bg-bg";
  return href ? (
    <Link href={href} className={cls}>
      {body}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {body}
    </button>
  );
}

export default function DevStates() {
  if (process.env.NODE_ENV === "production") notFound();

  const [sheet, setSheet] = useState<
    "methods" | "receipt-loading" | "receipt-confirm" | "pick-product" | "type-idle" | "type-recording" | "deal-detail" | null
  >(null);
  // Starts as "system" to match the server-rendered markup, then syncs from localStorage after mount
  // (reading it during the initial render would mismatch SSR output and trigger a hydration error).
  const [theme, setTheme] = useState<"system" | "light" | "dark">("system");
  useEffect(() => setTheme(getForcedTheme()), []);
  const { items, addItems, deleteItem } = useItems();
  const { data: deals } = useApi(() => api.GET("/deals", { params: withUser() }));
  const firstDeal = deals?.[0] ?? null;

  function pickTheme(t: "system" | "light" | "dark") {
    setForcedTheme(t);
    setTheme(t);
  }

  async function clearList() {
    for (const i of items ?? []) await deleteItem(i.user_item_id);
  }
  async function restoreDemoItems() {
    await addItems({ items: DEMO_SEED, source: "manual" });
  }

  return (
    <>
      <LargeTitle title="Dev states" />
      <p className="mx-4 mb-6 text-[15px] text-label-2">
        Not part of the app&apos;s navigation — a reviewer aid for reaching all 18 designed states. Most buttons drive the real
        sheets against the real (mock-mode) API.
      </p>

      <Section title="Theme override">
        <div className="flex gap-2 px-1 pb-1">
          {(["system", "light", "dark"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => pickTheme(t)}
              className={`flex-1 rounded-xl px-3 py-2.5 text-[15px] capitalize ${theme === t ? "bg-tint font-semibold text-white" : "bg-bg text-label"}`}
            >
              {t}
            </button>
          ))}
        </div>
      </Section>

      <Section title="My list">
        <DevButton href="/list" label="Populated" note="Screen 1 — the real route" />
        <DevButton
          label="Empty"
          note="Screen 2 — clears your real list so /list, /deals and /basket all show their empty state"
          onClick={clearList}
        />
        <DevButton label="Restore demo items" note="Undo the above" onClick={restoreDemoItems} />
        <DevButton label="Add to your list sheet" note="Screen 3" onClick={() => setSheet("methods")} />
        <DevButton href="/list" label="Dark" note="Screen 16 — set theme to Dark above, then open" />
      </Section>

      <Section title="Receipt flow">
        <DevButton label="Reading receipt (loading)" note="Screen 4" onClick={() => setSheet("receipt-loading")} />
        <DevButton label="Confirm receipt items" note="Screen 5 — tap Edit on a flagged row for Screen 6" onClick={() => setSheet("receipt-confirm")} />
        <DevButton
          href="/list"
          label="Or: scan a real receipt"
          note="Tap + → Scan a receipt and pick any photo — mock mode returns this same extraction"
        />
      </Section>

      <Section title="Pick product">
        <DevButton label="Which one is it?" note="Screen 7" onClick={() => setSheet("pick-product")} />
      </Section>

      <Section title="Type or say it">
        <DevButton label="Idle" note="Screen 8" onClick={() => setSheet("type-idle")} />
        <DevButton label="Recording (static preview)" note="Screen 9 — real mic needs permission; hold the mic in Idle for the live version" onClick={() => setSheet("type-recording")} />
        <DevButton label="Parsed" note="Screen 10 — type anything in Idle and press Enter" onClick={() => setSheet("type-idle")} />
      </Section>

      <Section title="Deals">
        <DevButton href="/deals" label="Populated" note="Screen 11" />
        <DevButton label="Milk deal detail" note="Screen 12 — uses your real cheapest deal" onClick={() => setSheet("deal-detail")} />
        <DevButton label="Empty" note="Screen 13 — see My List → Empty above" onClick={clearList} />
        <DevButton href="/deals" label="Dark" note="Screen 17 — set theme to Dark above, then open" />
      </Section>

      <Section title="Basket">
        <DevButton href="/basket" label="Populated" note="Screen 14" />
        <DevButton label="Empty" note="Screen 15 — see My List → Empty above" onClick={clearList} />
        <DevButton href="/basket" label="Dark" note="Screen 18 — set theme to Dark above, then open" />
      </Section>

      <div className="mx-4 mb-10 flex flex-col gap-4">
        <p className="text-[13px] font-semibold text-label-2 uppercase">Static previews (no data required)</p>
        <EmptyState icon={<ReceiptText size={52} />} title="Snap a receipt to fill your list." primaryLabel="Scan a receipt" secondaryLabel="Or add one item" />
        <EmptyState icon={<Tag size={52} />} title="No deals on your items this week." subtitle="New flyers land every Thursday." />
        <EmptyState icon={<ShoppingCart size={52} />} title="Add items to compare stores." primaryLabel="Add items" />
      </div>

      <AddMethodsSheet open={sheet === "methods"} onClose={() => setSheet(null)} onPick={() => setSheet(null)} />

      {sheet === "receipt-loading" && <ReceiptLoading previewUrl="/products/receipt-thumbnail.jpg" onCancel={() => setSheet(null)} />}

      {sheet === "receipt-confirm" && (
        <ReceiptConfirmSheet
          key="dev-receipt-confirm"
          open
          extraction={MOCK_RECEIPT}
          onClose={() => setSheet(null)}
          onSave={async (chosen) => {
            await addItems({ items: chosen, source: "receipt" });
            setSheet(null);
          }}
        />
      )}

      {sheet === "pick-product" && (
        <PickProductSheet
          key="dev-pick-product"
          open
          previewUrl="/products/olive-oil-bottle.jpg"
          candidates={MOCK_PRODUCT}
          onClose={() => setSheet(null)}
          onAdd={async (item) => {
            await addItems({ items: [item], source: "photo" });
            setSheet(null);
          }}
        />
      )}

      {(sheet === "type-idle" || sheet === "type-recording") && (
        <TypeOrSaySheet
          key={sheet}
          open
          previewStep={sheet === "type-recording" ? "recording" : undefined}
          onClose={() => setSheet(null)}
          onAdd={async (item, source) => {
            await addItems({ items: [item], source });
            setSheet(null);
          }}
        />
      )}

      {sheet === "deal-detail" && firstDeal && (
        <DealDetailSheet deal={firstDeal} others={(deals ?? []).filter((d) => d.item_label === firstDeal.item_label && d.flyer_item_id !== firstDeal.flyer_item_id)} onClose={() => setSheet(null)} />
      )}
    </>
  );
}
