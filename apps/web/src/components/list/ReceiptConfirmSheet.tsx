"use client";
// Confirm-items sheet: low-confidence lines ("CHECK THESE") always need a look and route to the edit
// form; everything else ("LOOKS RIGHT") is pre-selected with a tap-to-exclude checkmark, per the design.
import { useEffect, useRef, useState } from "react";
import { Sheet } from "@/components/Sheet";
import { InlineError, PrimaryButton, money } from "@/components/ui";
import { CircleCheck, TriangleAlert } from "@/components/icons";
import { ItemEditor, draftFrom, draftToItem, type ItemDraft } from "@/components/ItemEditor";
import { api, type Schemas } from "@/lib/api";
import { fullName } from "@/lib/format";

const CONFIRM_BELOW = 0.6;

function label(it: Schemas["ExtractedItem"]) {
  const size = it.size_qty && it.size_unit ? ` · ${it.size_qty} ${it.size_unit}` : "";
  return `${[it.brand, it.item, it.variant].filter(Boolean).join(" ")}${size}`;
}

type Similar = Schemas["FlyerGroup"];

/**
 * For each scanned line, the cheapest similar item on sale right now. It is the Flyers tab's own search, so it follows
 * the same ranking, and it looks at the product name only: a receipt rarely has the brand or size a flyer prints.
 * Looked up once per name (a cache), so editing a line does not repeat the others.
 */
function useSimilarDeals(items: Schemas["ExtractedItem"][]) {
  const cache = useRef(new Map<string, Similar | null>());
  const mounted = useRef(true);
  const [, refresh] = useState(0);
  const key = (it: Schemas["ExtractedItem"]) => it.item.trim().toLowerCase();

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const todo = [...new Set(items.map(key))].filter((q) => q && !cache.current.has(q));
    if (todo.length === 0) return;
    Promise.all(
      todo.map((q) =>
        api
          .GET("/flyer-items", { params: { query: { q, sort: "relevance", page_size: 1 } } })
          .then(({ data }) => cache.current.set(q, data?.items[0] ?? null))
          .catch(() => cache.current.set(q, null)), // a failed lookup just shows no line; it is never an error
      ),
    ).then(() => mounted.current && refresh((n) => n + 1));
  }, [items]);

  return (it: Schemas["ExtractedItem"]) => cache.current.get(key(it)) ?? null;
}

function SimilarDeal({ deal }: { deal: Similar | null }) {
  if (!deal) return null;
  const { cheapest } = deal;
  return (
    <p className="text-[13px] leading-snug font-medium text-savings-text">
      On sale: {fullName(deal)} · {money(cheapest.price)} at {cheapest.store}
    </p>
  );
}

export function ReceiptConfirmSheet({
  open,
  extraction,
  onClose,
  onSave,
  saving,
  saveError,
  onRetrySave,
}: {
  open: boolean;
  extraction: Schemas["Extraction"];
  onClose: () => void;
  onSave: (items: Schemas["ExtractedItem"][]) => void;
  saving?: boolean;
  /** Set when the last onSave's /items call failed; "tap to retry" re-submits the same chosen items. */
  saveError?: string;
  onRetrySave?: () => void;
}) {
  const [items, setItems] = useState(extraction.items);
  const [selected, setSelected] = useState<Set<number>>(() => new Set(extraction.items.map((_, i) => i)));
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState<ItemDraft | null>(null);
  const similarTo = useSimilarDeals(items);

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
  // Parsed with an explicit local time-of-day: a bare "2026-11-06" is parsed as UTC midnight, which
  // renders as the previous day in any timezone west of UTC (Vancouver included).
  const when = extraction.bought_at ? new Date(`${extraction.bought_at.slice(0, 10)}T00:00:00`) : null;
  const date =
    when && !Number.isNaN(when.getTime())
      ? when.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      : undefined; // an unreadable date is left out rather than shown as "Invalid Date"
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
            <div className="overflow-hidden rounded-[16px] border border-warning-border bg-warning-bg shadow-card">
              {low.map(({ it, i }) => (
                <div key={i} className="flex items-center gap-2 border-b border-warning-border px-3.5 py-3 last:border-b-0">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[17px] font-semibold text-label">{label(it)}</p>
                    <SimilarDeal deal={similarTo(it)} />
                  </div>
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
            <div className="overflow-hidden rounded-[16px] border border-separator bg-elevated shadow-card">
              {ok.map(({ it, i }) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => toggle(i)}
                  className="flex min-h-12 w-full items-center gap-3 border-b border-separator px-3.5 py-2 last:border-b-0"
                >
                  <CircleCheck size={22} className={selected.has(i) ? "shrink-0 text-tint" : "shrink-0 text-label-2/40"} />
                  <div className="min-w-0 flex-1 text-left">
                    <p className="truncate text-[17px]">{label(it)}</p>
                    <SimilarDeal deal={similarTo(it)} />
                  </div>
                </button>
              ))}
            </div>
            <p className="pt-2 pl-4 text-[13px] text-label-2">Tap a checkmark to leave an item out.</p>
          </>
        )}

        <div className="flex flex-col gap-2 pt-6">
          {saveError && onRetrySave && <InlineError message={saveError} onRetry={onRetrySave} />}
          <PrimaryButton onClick={() => onSave(chosenItems)} disabled={chosenItems.length === 0} loading={saving}>
            Save {chosenItems.length} item{chosenItems.length === 1 ? "" : "s"}
          </PrimaryButton>
        </div>
      </div>
    </Sheet>
  );
}
