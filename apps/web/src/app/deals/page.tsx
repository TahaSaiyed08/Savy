"use client";
import { useMemo, useState } from "react";
import { Chip, EmptyState, LargeTitle, RetryButton, Skeleton, Status } from "@/components/ui";
import { Tag } from "@/components/icons";
import { DealCard } from "@/components/deals/DealCard";
import { DealDetailSheet, formatValidity } from "@/components/deals/DealDetailSheet";
import { api, withUser, type Schemas } from "@/lib/api";
import { useApi } from "@/lib/use-api";

const ALL = "All stores";

function DealsSkeleton() {
  return (
    <div className="flex flex-col gap-6 pt-2 pb-8">
      {[0, 1].map((g) => (
        <div key={g} className="flex flex-col gap-3">
          <div className="flex items-center gap-3 px-4">
            <Skeleton className="h-[13px] w-24" />
          </div>
          <div className="flex gap-3 overflow-x-auto px-4 pb-1">
            {[0, 1, 2].map((c) => (
              <div key={c} className="flex w-[150px] shrink-0 flex-col gap-2.5 overflow-hidden rounded-2xl border border-separator bg-elevated p-0">
                <Skeleton className="size-[150px] rounded-none" />
                <div className="flex flex-col gap-2 p-2.5">
                  <Skeleton className="h-6 w-16" />
                  <Skeleton className="h-3 w-20" />
                  <Skeleton className="h-3 w-full" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Deals() {
  const { data, loading, error, refetch } = useApi(() => api.GET("/deals", { params: withUser() }));
  const [store, setStore] = useState<string>(ALL);
  const [active, setActive] = useState<Schemas["Deal"] | null>(null);

  const stores = useMemo(() => Array.from(new Set((data ?? []).map((d) => d.store))).sort(), [data]);

  const groups = useMemo(() => {
    const byItem: Record<string, Schemas["Deal"][]> = {};
    for (const d of data ?? []) (byItem[d.item_label] ??= []).push(d);
    return Object.entries(byItem).map(([item, deals]) => {
      const sorted = [...deals].sort((a, b) => (a.unit_price ?? Infinity) - (b.unit_price ?? Infinity));
      const visible = store === ALL ? sorted : sorted.filter((d) => d.store === store);
      return { item, sorted, visible, cheapestId: sorted[0]?.flyer_item_id };
    });
  }, [data, store]);
  const visibleGroups = groups.filter((g) => g.visible.length > 0);

  const activeGroup = active ? groups.find((g) => g.item === active.item_label) : undefined;
  const others = activeGroup ? activeGroup.sorted.filter((d) => d.flyer_item_id !== active!.flyer_item_id) : [];
  const validity = formatValidity(data?.[0]?.week_start);

  return (
    <>
      <LargeTitle
        title="Add item(s)"
        action={
          validity ? (
            <span className="rounded-full border border-savings-border bg-savings-bg px-2.5 py-1.5 text-[13px] text-savings-text">{validity}</span>
          ) : undefined
        }
      />

      {loading && (
        <>
          <p role="status" className="sr-only">
            Loading…
          </p>
          <DealsSkeleton />
        </>
      )}
      <Status error={error} />
      {error && <RetryButton onRetry={refetch} />}

      {!loading && !error && (data?.length ?? 0) === 0 && (
        <EmptyState icon={<Tag size={52} />} title="No deals on your items this week." subtitle="New flyers land every Thursday." />
      )}

      {!!data?.length && (
        <>
          <div className="flex gap-2 overflow-x-auto px-4 pb-2">
            <Chip label={ALL} selected={store === ALL} onClick={() => setStore(ALL)} />
            {stores.map((s) => (
              <Chip key={s} label={s} selected={store === s} onClick={() => setStore(s)} />
            ))}
          </div>

          <div className="flex flex-col gap-3 pt-1 pb-6">
            {visibleGroups.map((g) => (
              <div key={g.item} className="flex flex-col gap-1.5">
                <div className="flex items-center gap-3 px-4">
                  <p className="flex-1 text-[13px] font-semibold">{g.item.toUpperCase()}</p>
                  <p className="text-[11px] text-label-2">
                    {g.sorted.length} store{g.sorted.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="flex gap-2 overflow-x-auto px-4 pb-1">
                  {g.visible.map((d) => (
                    <DealCard
                      key={d.flyer_item_id}
                      deal={d}
                      isCheapest={d.flyer_item_id === g.cheapestId}
                      groupSize={g.sorted.length}
                      onClick={() => setActive(d)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <DealDetailSheet deal={active} others={others} onClose={() => setActive(null)} />
    </>
  );
}
