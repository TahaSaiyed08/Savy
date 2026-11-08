"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BasketRow } from "@/components/basket/BasketRow";
import { PriceMatch, matchFor, type MatchTarget } from "@/components/deals/PriceMatch";
import { ChevronRight, CircleCheck, ShoppingCart } from "@/components/icons";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useToast } from "@/components/Toast";
import { EmptyState, InsetGroup, LargeTitle, ListSkeleton, RetryButton, Status, money } from "@/components/ui";
import { useItems } from "@/lib/use-items";
import type { Schemas } from "@/lib/api";

const COLLAPSED_KEY = "realdeal.basket.doneCollapsed";

// The Pantry items moved here, as a shopping checklist. Done keeps a row here until cleared; it never leaves the Pantry.
export default function Basket() {
  const router = useRouter();
  const { items, loading, error, deleteError, deleteItem, setBasket, setDone, refetch } = useItems();
  const [match, setMatch] = useState<MatchTarget | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const toast = useToast();

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSED_KEY) === "1");
    } catch {
      // private mode: just start expanded
    }
  }, []);
  function toggleCollapsed() {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, c ? "0" : "1");
      } catch {
        // private mode: remembered for this visit only
      }
      return !c;
    });
  }

  const basket = items?.filter((i) => i.in_basket) ?? [];
  const toGet = basket.filter((i) => !i.done);
  const done = basket.filter((i) => i.done);
  const estimate = toGet.reduce((sum, i) => sum + (i.cheapest?.price ?? 0), 0);
  const saved = (list: Schemas["ListItem"][]) => list.reduce((sum, i) => sum + (i.saves_vs_next ?? 0), 0);

  const row = (i: Schemas["ListItem"]) => (
    <BasketRow
      key={i.user_item_id}
      item={i}
      onTap={() => setMatch(matchFor("Basket", i))}
      onToggleDone={() => setDone(i.user_item_id, !i.done)}
      onDelete={() => toast.show("Removed", deleteItem(i.user_item_id))}
    />
  );
  const clearDone = () => done.forEach((i) => setBasket(i.user_item_id, false));

  return (
    <>
      <LargeTitle
        title="Basket"
        leading={<ThemeToggle />}
        action={
          done.length > 0 ? (
            <button type="button" onClick={clearDone} className="min-h-tap text-[17px] text-tint">
              Clear done
            </button>
          ) : undefined
        }
      />
      {basket.length > 0 && (
        <p className="-mt-1 px-4 pb-3 text-[13px] text-label-2">
          {toGet.length} left · est. {money(estimate)}
          {saved(toGet) > 0 && ` · save ${money(saved(toGet))}`}
        </p>
      )}
      {loading && !items && <ListSkeleton rows={5} />}
      <Status error={error} />
      {error && <RetryButton onRetry={refetch} />}
      {deleteError && <p className="px-8 pb-4 text-center text-[13px] text-destructive">{deleteError}</p>}

      {!loading && !error && basket.length === 0 && (
        <EmptyState
          icon={<ShoppingCart size={52} />}
          title="Your basket is empty"
          subtitle="Move items here from your pantry when you're ready to shop."
          primaryLabel="Go to pantry"
          onPrimary={() => router.push("/list")}
        />
      )}

      {basket.length > 0 && toGet.length === 0 && (
        <EmptyState
          icon={<CircleCheck size={52} />}
          title="All done"
          subtitle={saved(done) > 0 ? `Nice, you saved ${money(saved(done))} this trip.` : "Everything's ticked off."}
          primaryLabel="Clear done items"
          onPrimary={clearDone}
        />
      )}

      {toGet.length > 0 && <InsetGroup header={`To get (${toGet.length})`}>{toGet.map(row)}</InsetGroup>}

      {done.length > 0 && (
        <section className="mx-4 mb-6">
          <button type="button" onClick={toggleCollapsed} aria-expanded={!collapsed} className="flex min-h-tap items-center gap-1 px-4 text-[0.8125rem] uppercase text-label-2">
            <ChevronRight size={14} className={`transition-transform ${collapsed ? "" : "rotate-90"}`} />
            Done ({done.length})
          </button>
          {!collapsed && <ul className="overflow-hidden rounded-[14px] bg-elevated">{done.map(row)}</ul>}
        </section>
      )}

      {toast.node}
      <PriceMatch target={match} onClose={() => setMatch(null)} />
    </>
  );
}
